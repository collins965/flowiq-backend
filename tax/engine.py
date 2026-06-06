"""
tax/engine.py

Kenya KRA Tax Engine — Accurate 2024/2025 rates.

Handles:
- PAYE calculation with progressive bands
- NHIF deduction (income-based tiers)
- NSSF Tier I and Tier II (NSSF Act 2013)
- Housing Levy (1.5% of gross)
- Housing Levy Relief (15% of levy paid)
- Personal Relief (KES 2,400/month)
- Turnover Tax for self-employed (1.5% of revenue)
- Combined employed + self-employed scenarios
"""

from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from typing import Optional


def d(value) -> Decimal:
    """Convert any number to Decimal safely."""
    return Decimal(str(value))


# ─────────────────────────────────────────────────────────────────────────────
# KRA 2024/2025 Rate Tables
# ─────────────────────────────────────────────────────────────────────────────

# PAYE bands (monthly, KES)
PAYE_BANDS = [
    (d(0),       d(24_000),   d("0.10")),
    (d(24_001),  d(32_333),   d("0.25")),
    (d(32_334),  d(500_000),  d("0.30")),
    (d(500_001), d(800_000),  d("0.325")),
    (d(800_001), None,        d("0.35")),
]

PERSONAL_RELIEF_MONTHLY = d(2_400)
HOUSING_LEVY_RATE = d("0.015")
HOUSING_LEVY_RELIEF_RATE = d("0.15")
HOUSING_LEVY_RELIEF_MAX_ANNUAL = d(108_000)

# NHIF tiers (monthly gross → monthly deduction)
NHIF_TIERS = [
    (d(0),       d(5_999),   d(150)),
    (d(6_000),   d(7_999),   d(300)),
    (d(8_000),   d(11_999),  d(400)),
    (d(12_000),  d(14_999),  d(500)),
    (d(15_000),  d(19_999),  d(600)),
    (d(20_000),  d(24_999),  d(750)),
    (d(25_000),  d(29_999),  d(850)),
    (d(30_000),  d(34_999),  d(900)),
    (d(35_000),  d(39_999),  d(950)),
    (d(40_000),  d(44_999),  d(1_000)),
    (d(45_000),  d(49_999),  d(1_100)),
    (d(50_000),  d(59_999),  d(1_200)),
    (d(60_000),  d(69_999),  d(1_300)),
    (d(70_000),  d(79_999),  d(1_400)),
    (d(80_000),  d(89_999),  d(1_500)),
    (d(90_000),  d(99_999),  d(1_600)),
    (d(100_000), None,       d(1_700)),
]

# NSSF Tier limits (monthly, KES)
NSSF_TIER_1_LIMIT = d(7_000)
NSSF_TIER_2_LIMIT = d(36_000)
NSSF_RATE = d("0.06")
NSSF_TIER_1_MAX = d(420)   # 6% of 7,000
NSSF_TIER_2_MAX = d(1_740) # 6% of (36,000 - 7,000)

# Turnover Tax (self-employed, annual revenue < KES 25M)
TURNOVER_TAX_RATE = d("0.015")
TURNOVER_TAX_THRESHOLD = d(25_000_000)  # annual


# ─────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TaxBreakdown:
    """Complete tax breakdown for one income source."""
    label: str
    gross_monthly: Decimal
    nssf_tier1: Decimal = d(0)
    nssf_tier2: Decimal = d(0)
    nssf_total: Decimal = d(0)
    taxable_income: Decimal = d(0)
    gross_paye: Decimal = d(0)
    personal_relief: Decimal = d(0)
    housing_levy_relief: Decimal = d(0)
    net_paye: Decimal = d(0)
    nhif: Decimal = d(0)
    housing_levy: Decimal = d(0)
    net_pay: Decimal = d(0)
    effective_rate: Decimal = d(0)
    marginal_rate: Decimal = d(0)
    paye_band_breakdown: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "gross_monthly": str(self.gross_monthly),
            "deductions": {
                "nssf_tier1": str(self.nssf_tier1),
                "nssf_tier2": str(self.nssf_tier2),
                "nssf_total": str(self.nssf_total),
                "housing_levy": str(self.housing_levy),
            },
            "taxable_income": str(self.taxable_income),
            "paye": {
                "gross_paye": str(self.gross_paye),
                "personal_relief": str(self.personal_relief),
                "housing_levy_relief": str(self.housing_levy_relief),
                "net_paye": str(self.net_paye),
                "band_breakdown": self.paye_band_breakdown,
            },
            "nhif": str(self.nhif),
            "net_pay": str(self.net_pay),
            "effective_rate_percent": str(self.effective_rate),
            "marginal_rate_percent": str(self.marginal_rate),
        }


@dataclass
class SelfEmployedBreakdown:
    """Tax breakdown for self-employed / turnover tax."""
    label: str
    annual_revenue: Decimal
    turnover_tax: Decimal = d(0)
    monthly_turnover_tax: Decimal = d(0)
    is_vat_registered: bool = False
    vat_threshold: Decimal = d(5_000_000)
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "annual_revenue": str(self.annual_revenue),
            "turnover_tax_annual": str(self.turnover_tax),
            "turnover_tax_monthly": str(self.monthly_turnover_tax),
            "rate": "1.5%",
            "is_vat_registered": self.is_vat_registered,
            "vat_threshold": str(self.vat_threshold),
            "note": self.note,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Core calculation functions
# ─────────────────────────────────────────────────────────────────────────────

def calculate_nssf(gross_monthly: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """
    Returns (tier1, tier2, total) NSSF deductions.
    Based on NSSF Act 2013.
    """
    tier1 = min(gross_monthly * NSSF_RATE, NSSF_TIER_1_MAX)

    if gross_monthly > NSSF_TIER_1_LIMIT:
        tier2_base = min(gross_monthly, NSSF_TIER_2_LIMIT) - NSSF_TIER_1_LIMIT
        tier2 = min(tier2_base * NSSF_RATE, NSSF_TIER_2_MAX)
    else:
        tier2 = d(0)

    total = tier1 + tier2
    return (
        tier1.quantize(d("0.01"), ROUND_HALF_UP),
        tier2.quantize(d("0.01"), ROUND_HALF_UP),
        total.quantize(d("0.01"), ROUND_HALF_UP),
    )


def calculate_nhif(gross_monthly: Decimal) -> Decimal:
    """Returns NHIF deduction based on income tier."""
    for lower, upper, amount in NHIF_TIERS:
        if upper is None:
            return amount
        if lower <= gross_monthly <= upper:
            return amount
    return d(1_700)  # max tier fallback


def calculate_housing_levy(gross_monthly: Decimal) -> Decimal:
    """Returns 1.5% of gross salary."""
    return (gross_monthly * HOUSING_LEVY_RATE).quantize(d("0.01"), ROUND_HALF_UP)


def calculate_paye(taxable_income: Decimal) -> tuple[Decimal, list, Decimal]:
    """
    Progressive PAYE calculation.
    Returns (gross_paye, band_breakdown, marginal_rate).
    """
    total_tax = d(0)
    breakdown = []
    marginal_rate = d(0)

    for lower, upper, rate in PAYE_BANDS:
        if taxable_income <= lower:
            break

        band_upper = upper if upper is not None else taxable_income
        taxable_in_band = min(taxable_income, band_upper) - lower
        if taxable_in_band <= 0:
            continue

        tax_in_band = taxable_in_band * rate
        total_tax += tax_in_band
        marginal_rate = rate * 100

        breakdown.append({
            "band": f"KES {lower:,.0f} – {f'{band_upper:,.0f}' if upper else 'above'}",
            "rate": f"{rate * 100:.1f}%",
            "taxable_amount": str(taxable_in_band.quantize(d("0.01"))),
            "tax": str(tax_in_band.quantize(d("0.01"))),
        })

    return (
        total_tax.quantize(d("0.01"), ROUND_HALF_UP),
        breakdown,
        marginal_rate,
    )


def calculate_employed(gross_monthly: Decimal, label: str = "Employment Income") -> TaxBreakdown:
    """
    Full PAYE calculation for an employed individual.
    """
    gross_monthly = d(gross_monthly)

    # Step 1: NSSF
    nssf_t1, nssf_t2, nssf_total = calculate_nssf(gross_monthly)

    # Step 2: Taxable income (gross minus NSSF)
    taxable_income = max(d(0), gross_monthly - nssf_total)

    # Step 3: Gross PAYE
    gross_paye, band_breakdown, marginal_rate = calculate_paye(taxable_income)

    # Step 4: Housing levy
    housing_levy = calculate_housing_levy(gross_monthly)

    # Step 5: Housing levy relief (15% of levy, max KES 9,000/month)
    housing_levy_relief = min(
        housing_levy * HOUSING_LEVY_RELIEF_RATE,
        HOUSING_LEVY_RELIEF_MAX_ANNUAL / 12,
    ).quantize(d("0.01"), ROUND_HALF_UP)

    # Step 6: Net PAYE (after personal relief and housing levy relief)
    net_paye = max(
        d(0),
        gross_paye - PERSONAL_RELIEF_MONTHLY - housing_levy_relief
    ).quantize(d("0.01"), ROUND_HALF_UP)

    # Step 7: NHIF
    nhif = calculate_nhif(gross_monthly)

    # Step 8: Net pay
    net_pay = (
        gross_monthly - nssf_total - net_paye - nhif - housing_levy
    ).quantize(d("0.01"), ROUND_HALF_UP)

    # Effective rate
    total_deductions = nssf_total + net_paye + nhif + housing_levy
    effective_rate = (
        total_deductions / gross_monthly * 100
        if gross_monthly > 0 else d(0)
    ).quantize(d("0.01"), ROUND_HALF_UP)

    return TaxBreakdown(
        label=label,
        gross_monthly=gross_monthly,
        nssf_tier1=nssf_t1,
        nssf_tier2=nssf_t2,
        nssf_total=nssf_total,
        taxable_income=taxable_income,
        gross_paye=gross_paye,
        personal_relief=PERSONAL_RELIEF_MONTHLY,
        housing_levy_relief=housing_levy_relief,
        net_paye=net_paye,
        nhif=nhif,
        housing_levy=housing_levy,
        net_pay=net_pay,
        effective_rate=effective_rate,
        marginal_rate=d(marginal_rate),
        paye_band_breakdown=band_breakdown,
    )


def calculate_self_employed(
    annual_revenue: Decimal,
    label: str = "Business Income",
) -> SelfEmployedBreakdown:
    """
    Turnover Tax calculation for self-employed individuals.
    1.5% of gross revenue if annual revenue < KES 25,000,000.
    """
    annual_revenue = d(annual_revenue)
    monthly_revenue = annual_revenue / 12

    if annual_revenue >= TURNOVER_TAX_THRESHOLD:
        note = (
            "Your annual revenue exceeds KES 25,000,000. "
            "You are subject to standard income tax rates, not Turnover Tax. "
            "Consult a certified public accountant for accurate computation."
        )
        turnover_tax = d(0)
        monthly_tax = d(0)
    else:
        turnover_tax = (annual_revenue * TURNOVER_TAX_RATE).quantize(
            d("0.01"), ROUND_HALF_UP
        )
        monthly_tax = (turnover_tax / 12).quantize(d("0.01"), ROUND_HALF_UP)
        note = (
            f"Turnover Tax applies at 1.5% of gross revenue. "
            f"Annual liability: KES {turnover_tax:,.2f}. "
            f"Pay quarterly via iTax."
        )

    is_vat = annual_revenue >= d(5_000_000)

    return SelfEmployedBreakdown(
        label=label,
        annual_revenue=annual_revenue,
        turnover_tax=turnover_tax,
        monthly_turnover_tax=monthly_tax,
        is_vat_registered=is_vat,
        note=note,
    )


def calculate_combined(
    gross_monthly_salary: Decimal,
    annual_business_revenue: Decimal,
) -> dict:
    """
    Combined tax for employed + self-employed individuals.
    Employment income uses PAYE. Business income uses Turnover Tax.
    Returns a unified summary.
    """
    employment = calculate_employed(gross_monthly_salary, label="Employment Income")
    business = calculate_self_employed(annual_business_revenue, label="Business Income")

    total_monthly_tax = (
        employment.net_paye
        + employment.nhif
        + employment.nssf_total
        + employment.housing_levy
        + business.monthly_turnover_tax
    )

    total_monthly_income = employment.gross_monthly + (d(annual_business_revenue) / 12)
    combined_effective_rate = (
        total_monthly_tax / total_monthly_income * 100
        if total_monthly_income > 0 else d(0)
    ).quantize(d("0.01"))

    return {
        "employment": employment.to_dict(),
        "business": business.to_dict(),
        "combined_summary": {
            "total_monthly_income": str(total_monthly_income.quantize(d("0.01"))),
            "total_monthly_tax_burden": str(total_monthly_tax.quantize(d("0.01"))),
            "employment_net_pay": str(employment.net_pay),
            "business_monthly_tax": str(business.monthly_turnover_tax),
            "combined_effective_rate_percent": str(combined_effective_rate),
            "note": (
                "Employment income is taxed via PAYE by your employer. "
                "Business income is taxed via Turnover Tax paid directly to KRA."
            ),
        },
    }