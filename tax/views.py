from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status

# ─────────────────────────────────────────────
# KENYA — KRA 2024/2025
# ─────────────────────────────────────────────
KE_PAYE_BANDS = [
    {"lower": 0,      "upper": 24000,       "rate": 0.10},
    {"lower": 24001,  "upper": 32333,       "rate": 0.25},
    {"lower": 32334,  "upper": 500000,      "rate": 0.30},
    {"lower": 500001, "upper": 800000,      "rate": 0.325},
    {"lower": 800001, "upper": float("inf"),"rate": 0.35},
]
KE_PERSONAL_RELIEF = 2400
KE_NHIF_TABLE = [
    {"max": 5999,         "amount": 150},
    {"max": 7999,         "amount": 300},
    {"max": 11999,        "amount": 400},
    {"max": 14999,        "amount": 500},
    {"max": 19999,        "amount": 600},
    {"max": 24999,        "amount": 750},
    {"max": 29999,        "amount": 850},
    {"max": 34999,        "amount": 900},
    {"max": 39999,        "amount": 950},
    {"max": 44999,        "amount": 1000},
    {"max": 49999,        "amount": 1100},
    {"max": 59999,        "amount": 1200},
    {"max": 69999,        "amount": 1300},
    {"max": 79999,        "amount": 1400},
    {"max": 89999,        "amount": 1500},
    {"max": 99999,        "amount": 1600},
    {"max": float("inf"),"amount": 1700},
]

# ─────────────────────────────────────────────
# COUNTRY TAX CONFIGS
# Annual income bands → converted to monthly internally
# ─────────────────────────────────────────────
COUNTRY_TAX_CONFIGS = {
    # USA — Federal income tax 2024 (single filer, annual)
    "US": {
        "name": "United States",
        "currency": "USD",
        "bands": [
            {"lower": 0,       "upper": 11600,  "rate": 0.10},
            {"lower": 11600,   "upper": 47150,  "rate": 0.12},
            {"lower": 47150,   "upper": 100525, "rate": 0.22},
            {"lower": 100525,  "upper": 191950, "rate": 0.24},
            {"lower": 191950,  "upper": 243725, "rate": 0.32},
            {"lower": 243725,  "upper": 609350, "rate": 0.35},
            {"lower": 609350,  "upper": float("inf"), "rate": 0.37},
        ],
        "standard_deduction": 14600,  # annual
        "social_security_rate": 0.062,
        "social_security_cap": 160200,
        "medicare_rate": 0.0145,
        "notes": "Federal tax only. State taxes vary.",
    },
    # UK — PAYE 2024/25 (annual)
    "GB": {
        "name": "United Kingdom",
        "currency": "GBP",
        "bands": [
            {"lower": 0,      "upper": 12570,  "rate": 0.0},
            {"lower": 12570,  "upper": 50270,  "rate": 0.20},
            {"lower": 50270,  "upper": 125140, "rate": 0.40},
            {"lower": 125140, "upper": float("inf"), "rate": 0.45},
        ],
        "ni_rate": 0.08,
        "ni_threshold": 12570,
        "notes": "Includes National Insurance (8% above threshold).",
    },
    # Canada — Federal 2024 (annual)
    "CA": {
        "name": "Canada",
        "currency": "CAD",
        "bands": [
            {"lower": 0,       "upper": 55867,  "rate": 0.15},
            {"lower": 55867,   "upper": 111733, "rate": 0.205},
            {"lower": 111733,  "upper": 154906, "rate": 0.26},
            {"lower": 154906,  "upper": 220000, "rate": 0.29},
            {"lower": 220000,  "upper": float("inf"), "rate": 0.33},
        ],
        "basic_personal_amount": 15705,
        "cpp_rate": 0.0595,
        "cpp_cap": 68500,
        "ei_rate": 0.0166,
        "notes": "Federal tax only. Provincial taxes vary.",
    },
    # Australia — ATO 2024/25 (annual)
    "AU": {
        "name": "Australia",
        "currency": "AUD",
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
    # Germany — simplified 2024 (annual)
    "DE": {
        "name": "Germany",
        "currency": "EUR",
        "bands": [
            {"lower": 0,       "upper": 11604,  "rate": 0.0},
            {"lower": 11604,   "upper": 66760,  "rate": 0.14},
            {"lower": 66760,   "upper": 277826, "rate": 0.42},
            {"lower": 277826,  "upper": float("inf"), "rate": 0.45},
        ],
        "solidarity_surcharge": 0.055,
        "social_security_rate": 0.195,
        "notes": "Includes solidarity surcharge. Social security approx 19.5%.",
    },
    # Nigeria — PITA (annual)
    "NG": {
        "name": "Nigeria",
        "currency": "NGN",
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
    # South Africa — SARS 2024/25 (annual)
    "ZA": {
        "name": "South Africa",
        "currency": "ZAR",
        "bands": [
            {"lower": 0,        "upper": 237100,  "rate": 0.18},
            {"lower": 237100,   "upper": 370500,  "rate": 0.26},
            {"lower": 370500,   "upper": 512800,  "rate": 0.31},
            {"lower": 512800,   "upper": 673000,  "rate": 0.36},
            {"lower": 673000,   "upper": 857900,  "rate": 0.39},
            {"lower": 857900,   "upper": 1817000, "rate": 0.41},
            {"lower": 1817000,  "upper": float("inf"), "rate": 0.45},
        ],
        "primary_rebate": 17235,
        "uif_rate": 0.01,
        "uif_cap": 177624,
        "notes": "UIF contribution 1% capped at ZAR 177,624 annual.",
    },
    # Ghana — GRA 2024 (annual)
    "GH": {
        "name": "Ghana",
        "currency": "GHS",
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
    # Uganda — URA 2024/25 (annual)
    "UG": {
        "name": "Uganda",
        "currency": "UGX",
        "bands": [
            {"lower": 0,          "upper": 2820000,  "rate": 0.0},
            {"lower": 2820000,    "upper": 4920000,  "rate": 0.10},
            {"lower": 4920000,    "upper": 120000000,"rate": 0.20},
            {"lower": 120000000,  "upper": float("inf"), "rate": 0.30},
        ],
        "nssf_rate": 0.05,
        "notes": "NSSF employee contribution 5%.",
    },
    # Tanzania — TRA 2024 (annual)
    "TZ": {
        "name": "Tanzania",
        "currency": "TZS",
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
    # Rwanda — RRA 2024 (annual)
    "RW": {
        "name": "Rwanda",
        "currency": "RWF",
        "bands": [
            {"lower": 0,        "upper": 360000,  "rate": 0.0},
            {"lower": 360000,   "upper": 1200000, "rate": 0.20},
            {"lower": 1200000,  "upper": float("inf"), "rate": 0.30},
        ],
        "rssb_rate": 0.03,
        "notes": "RSSB employee pension 3%.",
    },
    # Ethiopia — ERCA (annual)
    "ET": {
        "name": "Ethiopia",
        "currency": "ETB",
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
    # India — New Tax Regime 2024/25 (annual, INR)
    "IN": {
        "name": "India",
        "currency": "INR",
        "bands": [
            {"lower": 0,        "upper": 300000,  "rate": 0.0},
            {"lower": 300000,   "upper": 600000,  "rate": 0.05},
            {"lower": 600000,   "upper": 900000,  "rate": 0.10},
            {"lower": 900000,   "upper": 1200000, "rate": 0.15},
            {"lower": 1200000,  "upper": 1500000, "rate": 0.20},
            {"lower": 1500000,  "upper": float("inf"), "rate": 0.30},
        ],
        "standard_deduction": 50000,
        "pf_rate": 0.12,
        "pf_cap": 1800000,
        "notes": "New tax regime. PF contribution 12% up to INR 15,000/month.",
    },
    # UAE — 0% income tax
    "AE": {
        "name": "United Arab Emirates",
        "currency": "AED",
        "bands": [
            {"lower": 0, "upper": float("inf"), "rate": 0.0},
        ],
        "notes": "No personal income tax in UAE.",
    },
    # France (annual)
    "FR": {
        "name": "France",
        "currency": "EUR",
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
    # Singapore (annual, SGD)
    "SG": {
        "name": "Singapore",
        "currency": "SGD",
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

# ─────────────────────────────────────────────
# FALLBACK — income-based flat rate estimate
# for countries not explicitly configured
# ─────────────────────────────────────────────
def get_fallback_rate(annual_income_usd: float) -> float:
    if annual_income_usd <= 10000:
        return 0.05
    elif annual_income_usd <= 25000:
        return 0.12
    elif annual_income_usd <= 50000:
        return 0.18
    elif annual_income_usd <= 100000:
        return 0.24
    elif annual_income_usd <= 200000:
        return 0.30
    else:
        return 0.35


# ─────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────
def calculate_progressive_tax(annual_income: float, bands: list) -> float:
    tax = 0
    prev = 0
    for band in bands:
        taxable = min(max(annual_income - prev, 0), band["upper"] - band["lower"])
        tax += taxable * band["rate"]
        prev = band["upper"]
        if annual_income <= band["upper"]:
            break
    return tax


def get_marginal_rate(annual_income: float, bands: list) -> float:
    rate = 0
    for band in bands:
        if annual_income >= band["lower"]:
            rate = band["rate"] * 100
    return rate


# ─────────────────────────────────────────────
# KENYA-SPECIFIC HELPERS
# ─────────────────────────────────────────────
def calculate_ke_paye(monthly_gross: float) -> float:
    tax = 0
    remaining = monthly_gross
    prev = 0
    for band in KE_PAYE_BANDS:
        taxable = min(remaining, band["upper"] - prev)
        if taxable <= 0:
            break
        tax += taxable * band["rate"]
        remaining -= taxable
        prev = band["upper"]
    return max(0, tax - KE_PERSONAL_RELIEF)


def calculate_ke_nhif(monthly_gross: float) -> float:
    for tier in KE_NHIF_TABLE:
        if monthly_gross <= tier["max"]:
            return tier["amount"]
    return 1700


def calculate_ke_nssf(monthly_gross: float) -> dict:
    tier1 = min(monthly_gross, 7000) * 0.06
    tier2 = max(0, min(monthly_gross, 36000) - 7000) * 0.06
    return {"tier1": tier1, "tier2": tier2, "total": tier1 + tier2}


def calculate_ke_housing_levy(monthly_gross: float) -> dict:
    levy = monthly_gross * 0.015
    relief = min(levy * 0.15, 9000)
    return {"levy": levy, "relief": relief}


# ─────────────────────────────────────────────
# VIEW
# ─────────────────────────────────────────────
class TaxCalculateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        gross_monthly = float(data.get("gross_monthly", 0))
        side_income = float(data.get("side_hustle_income", 0))
        employment_type = data.get("employment_type", "employed")
        country = data.get("country", "KE").upper()

        total_monthly = side_income if employment_type == "self_employed" else gross_monthly
        annual_income = total_monthly * 12

        # ── KENYA ──────────────────────────────
        if country == "KE":
            return self._calculate_kenya(
                total_monthly, annual_income, employment_type, side_income
            )

        # ── KNOWN COUNTRY ──────────────────────
        if country in COUNTRY_TAX_CONFIGS:
            return self._calculate_known_country(
                country, total_monthly, annual_income
            )

        # ── FALLBACK ───────────────────────────
        return self._calculate_fallback(country, total_monthly, annual_income)

    def _calculate_kenya(self, monthly, annual, employment_type, side_income):
        paye = calculate_ke_paye(monthly)
        nhif = calculate_ke_nhif(monthly)
        nssf = calculate_ke_nssf(monthly)
        housing = calculate_ke_housing_levy(monthly)

        total_deductions = paye + nhif + nssf["total"] + housing["levy"]
        net_pay = monthly - total_deductions
        effective_rate = (total_deductions / monthly * 100) if monthly > 0 else 0

        turnover_tax = None
        if employment_type == "self_employed" and side_income * 12 < 25_000_000:
            turnover_tax = {
                "monthly": round(side_income * 0.015),
                "annual": round(side_income * 0.015 * 12),
                "label": "Turnover Tax (1.5%)",
            }

        result = {
            "country": "KE",
            "country_name": "Kenya",
            "currency": "KES",
            "gross_monthly": monthly,
            "gross_annual": annual,
            "employment_type": employment_type,
            "deductions": {
                "paye": {
                    "monthly": round(paye),
                    "annual": round(paye * 12),
                    "label": "PAYE Income Tax",
                },
                "nhif": {
                    "monthly": nhif,
                    "annual": nhif * 12,
                    "label": "NHIF (SHA)",
                },
                "nssf_tier1": {
                    "monthly": round(nssf["tier1"]),
                    "annual": round(nssf["tier1"] * 12),
                    "label": "NSSF Tier I",
                },
                "nssf_tier2": {
                    "monthly": round(nssf["tier2"]),
                    "annual": round(nssf["tier2"] * 12),
                    "label": "NSSF Tier II",
                },
                "housing_levy": {
                    "monthly": round(housing["levy"]),
                    "annual": round(housing["levy"] * 12),
                    "label": "Housing Levy (1.5%)",
                },
            },
            "reliefs": {
                "personal_relief": {
                    "monthly": KE_PERSONAL_RELIEF,
                    "annual": KE_PERSONAL_RELIEF * 12,
                    "label": "Personal Relief",
                },
                "housing_relief": {
                    "monthly": round(housing["relief"]),
                    "annual": round(housing["relief"] * 12),
                    "label": "Housing Levy Relief (15%)",
                },
            },
            "totals": {
                "total_deductions": round(total_deductions),
                "total_deductions_annual": round(total_deductions * 12),
                "net_pay": round(net_pay),
                "net_pay_annual": round(net_pay * 12),
                "effective_rate": round(effective_rate, 1),
                "marginal_rate": get_marginal_rate(monthly, KE_PAYE_BANDS),
            },
            "notes": "KRA 2024/2025 rates. Includes PAYE, NHIF(SHA), NSSF, Housing Levy.",
        }

        if turnover_tax:
            result["turnover_tax"] = turnover_tax

        return Response(result, status=status.HTTP_200_OK)

    def _calculate_known_country(self, country, monthly, annual):
        config = COUNTRY_TAX_CONFIGS[country]
        bands = config["bands"]

        # Tax is calculated on annual income
        income_tax_annual = calculate_progressive_tax(annual, bands)

        # Apply deductions/reliefs if configured
        standard_deduction = config.get("standard_deduction", 0)
        basic_personal = config.get("basic_personal_amount", 0)
        primary_rebate = config.get("primary_rebate", 0)
        consolidated_relief = config.get("consolidated_relief", 0)

        taxable_annual = max(0, annual - standard_deduction - basic_personal - consolidated_relief)
        income_tax_annual = max(0, calculate_progressive_tax(taxable_annual, bands) - primary_rebate)
        income_tax_monthly = income_tax_annual / 12

        # Social contributions
        social_monthly = 0

        # US: Social Security + Medicare
        if country == "US":
            ss = min(annual, config["social_security_cap"]) * config["social_security_rate"]
            medicare = annual * config["medicare_rate"]
            social_monthly = (ss + medicare) / 12

        # UK: National Insurance
        elif country == "GB":
            ni_annual = max(0, annual - config["ni_threshold"]) * config["ni_rate"]
            social_monthly = ni_annual / 12

        # Canada: CPP + EI
        elif country == "CA":
            cpp = min(annual, config["cpp_cap"]) * config["cpp_rate"]
            ei = annual * config["ei_rate"]
            social_monthly = (cpp + ei) / 12

        # Australia: Medicare Levy
        elif country == "AU":
            social_monthly = annual * config["medicare_levy"] / 12

        # Germany: Social Security
        elif country == "DE":
            social_monthly = annual * config["social_security_rate"] / 12

        # South Africa: UIF
        elif country == "ZA":
            uif = min(annual, config["uif_cap"]) * config["uif_rate"]
            social_monthly = uif / 12

        # Ghana: SSNIT
        elif country == "GH":
            social_monthly = annual * config["ssnit_rate"] / 12

        # Uganda/Tanzania: NSSF
        elif country in ("UG", "TZ"):
            social_monthly = annual * config["nssf_rate"] / 12

        # Rwanda: RSSB
        elif country == "RW":
            social_monthly = annual * config["rssb_rate"] / 12

        # Ethiopia: Pension
        elif country == "ET":
            social_monthly = annual * config["pension_rate"] / 12

        # India: PF
        elif country == "IN":
            pf_annual = min(annual, config["pf_cap"]) * config["pf_rate"]
            social_monthly = pf_annual / 12

        # Singapore: CPF
        elif country == "SG":
            social_monthly = annual * config["cpf_rate"] / 12

        # France: Social Security
        elif country == "FR":
            social_monthly = annual * config["social_security_rate"] / 12

        total_deductions_monthly = income_tax_monthly + social_monthly
        net_pay_monthly = monthly - total_deductions_monthly
        effective_rate = (total_deductions_monthly / monthly * 100) if monthly > 0 else 0

        return Response({
            "country": country,
            "country_name": config["name"],
            "currency": config["currency"],
            "gross_monthly": round(monthly, 2),
            "gross_annual": round(annual, 2),
            "deductions": {
                "income_tax": {
                    "monthly": round(income_tax_monthly, 2),
                    "annual": round(income_tax_annual, 2),
                    "label": "Income Tax",
                },
                "social_contributions": {
                    "monthly": round(social_monthly, 2),
                    "annual": round(social_monthly * 12, 2),
                    "label": "Social Security / Contributions",
                },
            },
            "totals": {
                "total_deductions": round(total_deductions_monthly, 2),
                "total_deductions_annual": round(total_deductions_monthly * 12, 2),
                "net_pay": round(net_pay_monthly, 2),
                "net_pay_annual": round(net_pay_monthly * 12, 2),
                "effective_rate": round(effective_rate, 1),
                "marginal_rate": get_marginal_rate(annual, bands),
            },
            "notes": config.get("notes", ""),
        }, status=status.HTTP_200_OK)

    def _calculate_fallback(self, country, monthly, annual):
        # Estimate USD equivalent (rough fallback)
        estimated_rate = get_fallback_rate(annual)
        estimated_tax_monthly = monthly * estimated_rate
        net_pay = monthly - estimated_tax_monthly

        return Response({
            "country": country,
            "country_name": "Unknown",
            "currency": "Local currency",
            "gross_monthly": monthly,
            "gross_annual": annual,
            "deductions": {
                "estimated_tax": {
                    "monthly": round(estimated_tax_monthly, 2),
                    "annual": round(estimated_tax_monthly * 12, 2),
                    "label": "Estimated Income Tax",
                },
            },
            "totals": {
                "total_deductions": round(estimated_tax_monthly, 2),
                "total_deductions_annual": round(estimated_tax_monthly * 12, 2),
                "net_pay": round(net_pay, 2),
                "net_pay_annual": round(net_pay * 12, 2),
                "effective_rate": round(estimated_rate * 100, 1),
                "marginal_rate": round(estimated_rate * 100, 1),
            },
            "notes": f"Estimated tax for {country}. Exact rates not yet configured. Results are approximate.",
        }, status=status.HTTP_200_OK)