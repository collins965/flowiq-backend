"""
tax/views.py

Endpoints:
  GET    /api/tax/settings/    → get or create tax settings
  PATCH  /api/tax/settings/    → update tax settings
  POST   /api/tax/calculate/   → run full tax calculation
  GET    /api/tax/history/     → past calculations
  GET    /api/tax/rates/       → KRA + global rate reference
"""

import logging
from datetime import date

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import TaxSettings, TaxCalculation
from .serializers import (
    TaxSettingsSerializer,
    TaxCalculateSerializer,
    TaxCalculationHistorySerializer,
)
from .engine import (
    calculate_employed,
    calculate_self_employed,
    calculate_combined,
    PAYE_BANDS,
    PERSONAL_RELIEF_MONTHLY,
    NHIF_TIERS,
    NSSF_TIER_1_MAX,
    NSSF_TIER_2_MAX,
    TURNOVER_TAX_RATE,
    d,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Global tax configurations
# All bands are ANNUAL income. Converted to monthly internally.
# ─────────────────────────────────────────────────────────────────────────────

COUNTRY_TAX_CONFIGS = {
    "US": {
        "name": "United States", "currency": "USD",
        "bands": [
            {"lower": 0,       "upper": 11600,  "rate": 0.10},
            {"lower": 11600,   "upper": 47150,  "rate": 0.12},
            {"lower": 47150,   "upper": 100525, "rate": 0.22},
            {"lower": 100525,  "upper": 191950, "rate": 0.24},
            {"lower": 191950,  "upper": 243725, "rate": 0.32},
            {"lower": 243725,  "upper": 609350, "rate": 0.35},
            {"lower": 609350,  "upper": float("inf"), "rate": 0.37},
        ],
        "standard_deduction": 14600,
        "social_security_rate": 0.062, "social_security_cap": 160200,
        "medicare_rate": 0.0145,
        "notes": "Federal tax only. State taxes vary.",
    },
    "GB": {
        "name": "United Kingdom", "currency": "GBP",
        "bands": [
            {"lower": 0,      "upper": 12570,  "rate": 0.0},
            {"lower": 12570,  "upper": 50270,  "rate": 0.20},
            {"lower": 50270,  "upper": 125140, "rate": 0.40},
            {"lower": 125140, "upper": float("inf"), "rate": 0.45},
        ],
        "ni_rate": 0.08, "ni_threshold": 12570,
        "notes": "Includes National Insurance (8% above threshold).",
    },
    "CA": {
        "name": "Canada", "currency": "CAD",
        "bands": [
            {"lower": 0,       "upper": 55867,  "rate": 0.15},
            {"lower": 55867,   "upper": 111733, "rate": 0.205},
            {"lower": 111733,  "upper": 154906, "rate": 0.26},
            {"lower": 154906,  "upper": 220000, "rate": 0.29},
            {"lower": 220000,  "upper": float("inf"), "rate": 0.33},
        ],
        "basic_personal_amount": 15705,
        "cpp_rate": 0.0595, "cpp_cap": 68500,
        "ei_rate": 0.0166,
        "notes": "Federal tax only. Provincial taxes vary.",
    },
    "AU": {
        "name": "Australia", "currency": "AUD",
        "bands": [
            {"lower": 0,       "upper": 18200,  "rate": 0.0},
            {"lower": 18200,   "upper": 45000,  "rate": 0.19},
            {"lower": 45000,   "upper": 120000, "rate": 0.325},
            {"lower": 120000,  "upper": 180000, "rate": 0.37},
            {"lower": 180000,  "upper": float("inf"), "rate": 0.45},
        ],
        "medicare_levy": 0.02,
        "notes": "Includes 2% Medicare Levy.",
    },
    "DE": {
        "name": "Germany", "currency": "EUR",
        "bands": [
            {"lower": 0,       "upper": 11604,  "rate": 0.0},
            {"lower": 11604,   "upper": 66760,  "rate": 0.14},
            {"lower": 66760,   "upper": 277826, "rate": 0.42},
            {"lower": 277826,  "upper": float("inf"), "rate": 0.45},
        ],
        "solidarity_surcharge": 0.055, "social_security_rate": 0.195,
        "notes": "Includes solidarity surcharge. Social security approx 19.5%.",
    },
    "NG": {
        "name": "Nigeria", "currency": "NGN",
        "bands": [
            {"lower": 0,         "upper": 300000,   "rate": 0.07},
            {"lower": 300000,    "upper": 600000,   "rate": 0.11},
            {"lower": 600000,    "upper": 1100000,  "rate": 0.15},
            {"lower": 1100000,   "upper": 1600000,  "rate": 0.19},
            {"lower": 1600000,   "upper": 3200000,  "rate": 0.21},
            {"lower": 3200000,   "upper": float("inf"), "rate": 0.24},
        ],
        "consolidated_relief": 200000,
        "notes": "Personal Income Tax Act. Consolidated Relief Allowance applies.",
    },
    "ZA": {
        "name": "South Africa", "currency": "ZAR",
        "bands": [
            {"lower": 0,        "upper": 237100,  "rate": 0.18},
            {"lower": 237100,   "upper": 370500,  "rate": 0.26},
            {"lower": 370500,   "upper": 512800,  "rate": 0.31},
            {"lower": 512800,   "upper": 673000,  "rate": 0.36},
            {"lower": 673000,   "upper": 857900,  "rate": 0.39},
            {"lower": 857900,   "upper": 1817000, "rate": 0.41},
            {"lower": 1817000,  "upper": float("inf"), "rate": 0.45},
        ],
        "primary_rebate": 17235, "uif_rate": 0.01, "uif_cap": 177624,
        "notes": "UIF contribution 1% capped at ZAR 177,624 annual.",
    },
    "GH": {
        "name": "Ghana", "currency": "GHS",
        "bands": [
            {"lower": 0,      "upper": 4380,   "rate": 0.0},
            {"lower": 4380,   "upper": 5460,   "rate": 0.05},
            {"lower": 5460,   "upper": 6960,   "rate": 0.10},
            {"lower": 6960,   "upper": 9960,   "rate": 0.175},
            {"lower": 9960,   "upper": 42960,  "rate": 0.25},
            {"lower": 42960,  "upper": 240000, "rate": 0.30},
            {"lower": 240000, "upper": float("inf"), "rate": 0.35},
        ],
        "ssnit_rate": 0.055,
        "notes": "SSNIT contribution 5.5% of gross.",
    },
    "UG": {
        "name": "Uganda", "currency": "UGX",
        "bands": [
            {"lower": 0,          "upper": 2820000,   "rate": 0.0},
            {"lower": 2820000,    "upper": 4920000,   "rate": 0.10},
            {"lower": 4920000,    "upper": 120000000, "rate": 0.20},
            {"lower": 120000000,  "upper": float("inf"), "rate": 0.30},
        ],
        "nssf_rate": 0.05,
        "notes": "NSSF employee contribution 5%.",
    },
    "TZ": {
        "name": "Tanzania", "currency": "TZS",
        "bands": [
            {"lower": 0,          "upper": 3240000,  "rate": 0.0},
            {"lower": 3240000,    "upper": 6240000,  "rate": 0.08},
            {"lower": 6240000,    "upper": 9240000,  "rate": 0.20},
            {"lower": 9240000,    "upper": 12240000, "rate": 0.25},
            {"lower": 12240000,   "upper": float("inf"), "rate": 0.30},
        ],
        "nssf_rate": 0.05,
        "notes": "NSSF employee contribution 5%.",
    },
    "RW": {
        "name": "Rwanda", "currency": "RWF",
        "bands": [
            {"lower": 0,        "upper": 360000,  "rate": 0.0},
            {"lower": 360000,   "upper": 1200000, "rate": 0.20},
            {"lower": 1200000,  "upper": float("inf"), "rate": 0.30},
        ],
        "rssb_rate": 0.03,
        "notes": "RSSB employee pension 3%.",
    },
    "ET": {
        "name": "Ethiopia", "currency": "ETB",
        "bands": [
            {"lower": 0,      "upper": 7200,   "rate": 0.0},
            {"lower": 7200,   "upper": 19800,  "rate": 0.10},
            {"lower": 19800,  "upper": 38400,  "rate": 0.15},
            {"lower": 38400,  "upper": 63000,  "rate": 0.20},
            {"lower": 63000,  "upper": 93600,  "rate": 0.25},
            {"lower": 93600,  "upper": 130800, "rate": 0.30},
            {"lower": 130800, "upper": float("inf"), "rate": 0.35},
        ],
        "pension_rate": 0.07,
        "notes": "Employee pension contribution 7%.",
    },
    "IN": {
        "name": "India", "currency": "INR",
        "bands": [
            {"lower": 0,        "upper": 300000,  "rate": 0.0},
            {"lower": 300000,   "upper": 600000,  "rate": 0.05},
            {"lower": 600000,   "upper": 900000,  "rate": 0.10},
            {"lower": 900000,   "upper": 1200000, "rate": 0.15},
            {"lower": 1200000,  "upper": 1500000, "rate": 0.20},
            {"lower": 1500000,  "upper": float("inf"), "rate": 0.30},
        ],
        "standard_deduction": 50000, "pf_rate": 0.12, "pf_cap": 1800000,
        "notes": "New tax regime. PF contribution 12% up to INR 15,000/month.",
    },
    "AE": {
        "name": "United Arab Emirates", "currency": "AED",
        "bands": [{"lower": 0, "upper": float("inf"), "rate": 0.0}],
        "notes": "No personal income tax in UAE.",
    },
    "FR": {
        "name": "France", "currency": "EUR",
        "bands": [
            {"lower": 0,       "upper": 11294,  "rate": 0.0},
            {"lower": 11294,   "upper": 28797,  "rate": 0.11},
            {"lower": 28797,   "upper": 82341,  "rate": 0.30},
            {"lower": 82341,   "upper": 177106, "rate": 0.41},
            {"lower": 177106,  "upper": float("inf"), "rate": 0.45},
        ],
        "social_security_rate": 0.22,
        "notes": "Includes approx 22% social contributions.",
    },
    "SG": {
        "name": "Singapore", "currency": "SGD",
        "bands": [
            {"lower": 0,       "upper": 20000,  "rate": 0.0},
            {"lower": 20000,   "upper": 30000,  "rate": 0.02},
            {"lower": 30000,   "upper": 40000,  "rate": 0.035},
            {"lower": 40000,   "upper": 80000,  "rate": 0.07},
            {"lower": 80000,   "upper": 120000, "rate": 0.115},
            {"lower": 120000,  "upper": 160000, "rate": 0.15},
            {"lower": 160000,  "upper": 200000, "rate": 0.18},
            {"lower": 200000,  "upper": 240000, "rate": 0.19},
            {"lower": 240000,  "upper": 280000, "rate": 0.195},
            {"lower": 280000,  "upper": 320000, "rate": 0.20},
            {"lower": 320000,  "upper": float("inf"), "rate": 0.22},
        ],
        "cpf_rate": 0.20,
        "notes": "CPF employee contribution 20% (age <55).",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def calculate_progressive_tax(annual_income: float, bands: list) -> float:
    tax = 0.0
    for band in bands:
        lower = band["lower"]
        upper = band["upper"]
        rate = band["rate"]
        if annual_income <= lower:
            break
        taxable = min(annual_income, upper) - lower
        if taxable > 0:
            tax += taxable * rate
    return tax


def get_marginal_rate(annual_income: float, bands: list) -> float:
    rate = 0.0
    for band in bands:
        if annual_income >= band["lower"]:
            rate = band["rate"] * 100
    return rate


def get_fallback_rate(annual_income: float) -> float:
    if annual_income <= 10000:
        return 0.05
    elif annual_income <= 25000:
        return 0.12
    elif annual_income <= 50000:
        return 0.18
    elif annual_income <= 100000:
        return 0.24
    elif annual_income <= 200000:
        return 0.30
    return 0.35


def calculate_social_contributions(country: str, config: dict, annual: float) -> float:
    """Calculate social security / contributions for known countries."""
    social = 0.0

    if country == "US":
        ss = min(annual, config["social_security_cap"]) * config["social_security_rate"]
        medicare = annual * config["medicare_rate"]
        social = ss + medicare
    elif country == "GB":
        social = max(0, annual - config["ni_threshold"]) * config["ni_rate"]
    elif country == "CA":
        cpp = min(annual, config["cpp_cap"]) * config["cpp_rate"]
        ei = annual * config["ei_rate"]
        social = cpp + ei
    elif country == "AU":
        social = annual * config["medicare_levy"]
    elif country in ("DE", "FR"):
        social = annual * config["social_security_rate"]
    elif country == "ZA":
        social = min(annual, config["uif_cap"]) * config["uif_rate"]
    elif country == "GH":
        social = annual * config["ssnit_rate"]
    elif country in ("UG", "TZ"):
        social = annual * config["nssf_rate"]
    elif country == "RW":
        social = annual * config["rssb_rate"]
    elif country == "ET":
        social = annual * config["pension_rate"]
    elif country == "IN":
        social = min(annual, config["pf_cap"]) * config["pf_rate"]
    elif country == "SG":
        social = annual * config["cpf_rate"]

    return social


# ─────────────────────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────────────────────

class TaxSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_or_create_settings(self, user):
        obj, _ = TaxSettings.objects.get_or_create(
            user=user,
            defaults={
                "country": "Kenya",
                "country_code": "KE",
                "tax_year": date.today().year,
            },
        )
        return obj

    def get(self, request):
        return Response(
            TaxSettingsSerializer(self._get_or_create_settings(request.user)).data
        )

    def patch(self, request):
        obj = self._get_or_create_settings(request.user)
        serializer = TaxSettingsSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(
            {"error": "Invalid data.", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class TaxCalculateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Accept both old-style (gross_monthly, country) and
        # new-style (employment_type, gross_monthly_salary, country_code) payloads
        data = request.data
        country_code = (
            data.get("country_code") or data.get("country", "KE")
        ).upper()
        employment_type = data.get("employment_type", "employed")
        tax_year = int(data.get("tax_year", date.today().year))

        # ── KENYA — use the precise KRA engine ───────────────────────────────
        if country_code == "KE":
            return self._calculate_kenya(request, data, employment_type, tax_year)

        # ── KNOWN COUNTRY — use configured bands ─────────────────────────────
        if country_code in COUNTRY_TAX_CONFIGS:
            return self._calculate_known_country(
                request, country_code, data, employment_type, tax_year
            )

        # ── FALLBACK ─────────────────────────────────────────────────────────
        return self._calculate_fallback(request, country_code, data, tax_year)

    # ── Kenya ─────────────────────────────────────────────────────────────────

    def _calculate_kenya(self, request, data, employment_type, tax_year):
        gross_monthly = float(
            data.get("gross_monthly_salary") or data.get("gross_monthly", 0)
        )
        annual_revenue = float(
            data.get("annual_business_revenue") or
            data.get("side_hustle_income", 0) * 12
        )

        if employment_type == "employed":
            result = calculate_employed(gross_monthly)
            breakdown = result.to_dict()
            net_paye = result.net_paye
            nhif = result.nhif
            nssf = result.nssf_total
            housing_levy = result.housing_levy
            net_pay = result.net_pay
            effective_rate = result.effective_rate
            gross_m = result.gross_monthly

        elif employment_type == "self_employed":
            result = calculate_self_employed(annual_revenue)
            breakdown = result.to_dict()
            gross_m = d(annual_revenue) / 12
            net_paye = d(0)
            nhif = d(0)
            nssf = d(0)
            housing_levy = d(0)
            net_pay = gross_m - result.monthly_turnover_tax
            effective_rate = (
                result.monthly_turnover_tax / gross_m * 100
                if gross_m > 0 else d(0)
            )

        else:  # both
            combined = calculate_combined(gross_monthly, annual_revenue)
            breakdown = combined
            emp = calculate_employed(gross_monthly)
            biz = calculate_self_employed(annual_revenue)
            gross_m = emp.gross_monthly + d(annual_revenue) / 12
            net_paye = emp.net_paye
            nhif = emp.nhif
            nssf = emp.nssf_total
            housing_levy = emp.housing_levy
            net_pay = emp.net_pay - biz.monthly_turnover_tax
            effective_rate = emp.effective_rate

        self._save_history(
            request.user, "KE", employment_type, tax_year,
            gross_m, breakdown, net_paye, nhif, nssf, housing_levy,
            net_pay, effective_rate,
        )

        return Response({
            "country_code": "KE",
            "country_name": "Kenya",
            "currency": "KES",
            "employment_type": employment_type,
            "tax_year": tax_year,
            "breakdown": breakdown,
            "summary": {
                "gross_monthly_income": str(gross_m),
                "net_paye": str(net_paye),
                "nhif": str(nhif),
                "nssf": str(nssf),
                "housing_levy": str(housing_levy),
                "net_pay": str(net_pay),
                "effective_tax_rate_percent": str(effective_rate),
            },
            "disclaimer": (
                "KRA 2024/2025 rates. Verify with your employer or a certified "
                "tax advisor before filing."
            ),
        })

    # ── Known country ─────────────────────────────────────────────────────────

    def _calculate_known_country(self, request, country_code, data, employment_type, tax_year):
        config = COUNTRY_TAX_CONFIGS[country_code]
        monthly = float(
            data.get("gross_monthly_salary") or data.get("gross_monthly", 0)
        )
        annual = monthly * 12

        # Apply deductions/reliefs
        standard_deduction = config.get("standard_deduction", 0)
        basic_personal = config.get("basic_personal_amount", 0)
        consolidated_relief = config.get("consolidated_relief", 0)
        primary_rebate = config.get("primary_rebate", 0)

        taxable_annual = max(
            0, annual - standard_deduction - basic_personal - consolidated_relief
        )
        income_tax_annual = max(
            0,
            calculate_progressive_tax(taxable_annual, config["bands"]) - primary_rebate
        )
        income_tax_monthly = income_tax_annual / 12

        social_annual = calculate_social_contributions(country_code, config, annual)
        social_monthly = social_annual / 12

        total_deductions = income_tax_monthly + social_monthly
        net_pay = monthly - total_deductions
        effective_rate = (total_deductions / monthly * 100) if monthly > 0 else 0

        self._save_history(
            request.user, country_code, employment_type, tax_year,
            d(monthly), {}, d(income_tax_monthly), d(0), d(social_monthly),
            d(0), d(net_pay), d(effective_rate),
        )

        return Response({
            "country_code": country_code,
            "country_name": config["name"],
            "currency": config["currency"],
            "employment_type": employment_type,
            "tax_year": tax_year,
            "deductions": {
                "income_tax": {
                    "monthly": round(income_tax_monthly, 2),
                    "annual": round(income_tax_annual, 2),
                    "label": "Income Tax",
                },
                "social_contributions": {
                    "monthly": round(social_monthly, 2),
                    "annual": round(social_annual, 2),
                    "label": "Social Security / Contributions",
                },
            },
            "summary": {
                "gross_monthly_income": round(monthly, 2),
                "total_deductions": round(total_deductions, 2),
                "net_pay": round(net_pay, 2),
                "net_pay_annual": round(net_pay * 12, 2),
                "effective_tax_rate_percent": round(effective_rate, 1),
                "marginal_rate_percent": get_marginal_rate(annual, config["bands"]),
            },
            "notes": config.get("notes", ""),
            "disclaimer": "Rates are approximate. Consult a local tax advisor for accuracy.",
        })

    # ── Fallback ──────────────────────────────────────────────────────────────

    def _calculate_fallback(self, request, country_code, data, tax_year):
        monthly = float(
            data.get("gross_monthly_salary") or data.get("gross_monthly", 0)
        )
        annual = monthly * 12
        rate = get_fallback_rate(annual)
        estimated_tax = monthly * rate
        net_pay = monthly - estimated_tax

        return Response({
            "country_code": country_code,
            "country_name": "Unknown",
            "currency": "Local currency",
            "tax_year": tax_year,
            "deductions": {
                "estimated_tax": {
                    "monthly": round(estimated_tax, 2),
                    "annual": round(estimated_tax * 12, 2),
                    "label": "Estimated Income Tax",
                },
            },
            "summary": {
                "gross_monthly_income": round(monthly, 2),
                "net_pay": round(net_pay, 2),
                "effective_tax_rate_percent": round(rate * 100, 1),
            },
            "notes": (
                f"Tax rates for {country_code} are not yet configured. "
                "This is a rough estimate only. Consult your local tax authority."
            ),
        })

    # ── Save to history ───────────────────────────────────────────────────────

    def _save_history(
        self, user, country_code, employment_type, tax_year,
        gross_monthly, breakdown, net_paye, nhif, nssf,
        housing_levy, net_pay, effective_rate,
    ):
        try:
            TaxCalculation.objects.create(
                user=user,
                country_code=country_code,
                employment_type=employment_type,
                tax_year=tax_year,
                gross_monthly_income=gross_monthly,
                breakdown=breakdown if isinstance(breakdown, dict) else {},
                net_paye=net_paye,
                nhif=nhif,
                nssf=nssf,
                housing_levy=housing_levy,
                net_pay=net_pay,
                effective_tax_rate=effective_rate,
            )
        except Exception as e:
            logger.warning("Failed to save tax calculation history: %s", e)


class TaxHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        calculations = TaxCalculation.objects.filter(
            user=request.user
        ).order_by("-created_at")[:20]
        serializer = TaxCalculationHistorySerializer(calculations, many=True)
        return Response({
            "calculations": serializer.data,
            "count": calculations.count(),
        })


class TaxRatesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        paye_bands = [
            {
                "from": str(lower),
                "to": str(upper) if upper else "Above",
                "rate": f"{rate * 100:.1f}%",
            }
            for lower, upper, rate in PAYE_BANDS
        ]
        nhif_tiers = [
            {
                "income_from": str(lower),
                "income_to": str(upper) if upper else "Above",
                "deduction": str(amount),
            }
            for lower, upper, amount in NHIF_TIERS
        ]
        supported_countries = [
            {"code": code, "name": cfg["name"], "currency": cfg["currency"]}
            for code, cfg in COUNTRY_TAX_CONFIGS.items()
        ]
        return Response({
            "kenya": {
                "authority": "Kenya Revenue Authority (KRA)",
                "tax_year": "2024/2025",
                "paye_bands": paye_bands,
                "personal_relief_monthly": str(PERSONAL_RELIEF_MONTHLY),
                "nhif_tiers": nhif_tiers,
                "nssf": {
                    "tier1_max_monthly": str(NSSF_TIER_1_MAX),
                    "tier2_max_monthly": str(NSSF_TIER_2_MAX),
                    "rate": "6% per tier",
                },
                "housing_levy": "1.5% of gross salary",
                "housing_levy_relief": "15% of levy paid (max KES 108,000/year)",
                "turnover_tax": f"{TURNOVER_TAX_RATE * 100:.1f}% (revenue < KES 25M/year)",
                "vat": "16% standard rate (registration if supplies > KES 5M/year)",
                "last_updated": "2024-07-01",
                "source": "kra.go.ke",
            },
            "supported_countries": supported_countries,
            "total_countries_supported": len(supported_countries),
        })