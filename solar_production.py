from typing import Literal

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt


def calculate_solar_economics(
    production_hourly: pd.Series,  # kWh/hour for one year (DatetimeIndex)
    spot_price_hourly: pd.Series,  # NOK/kWh/hour for one year (DatetimeIndex)
    consumption_hourly: pd.Series,  # kWh/hour for one year (DatetimeIndex)
    investment_cost: float,
    lifetime_years: int = 25,
    degradation_per_year: float = 0.005,
    grid_tariff: float = 0.49 * 0.8,  # NOK/kWh - 25% vat
    system_losses: float = 0.14,
    norges_pris: Literal[False] | float = False,
    inflation=0.03,
):
    """
    Calculates the financial performance of a solar PV system
    based on hourly time series for a representative year.
    Series must have a DatetimeIndex covering one year (8760 hours).
    """

    # Input checks
    assert isinstance(production_hourly.index, pd.DatetimeIndex), "Production must have DatetimeIndex"
    assert isinstance(spot_price_hourly.index, pd.DatetimeIndex), "Spot price must have DatetimeIndex"
    assert isinstance(consumption_hourly.index, pd.DatetimeIndex), "Consumption must have DatetimeIndex"
    assert len(production_hourly) == len(spot_price_hourly) == len(consumption_hourly), (
        "All time series must be the same length"
    )

    # Ensure sorted index
    production_hourly = production_hourly.sort_index()
    spot_price_hourly = spot_price_hourly.sort_index()
    consumption_hourly = consumption_hourly.sort_index()

    results = []
    cumulative_cashflow = 0
    payback_years = None

    # Apply system losses to the base year
    base_production = production_hourly * (1 - system_losses)

    for year in range(1, lifetime_years + 1):
        # Apply degradation
        degradation_factor = (1 - degradation_per_year) ** (year - 1)
        yearly_production = base_production * degradation_factor

        # Self-consumption = min(production, consumption) each hour
        self_consumption_series = yearly_production.combine(consumption_hourly, min)
        self_consumption_kWh = self_consumption_series.sum()

        # Surplus to grid
        surplus_series = (yearly_production - consumption_hourly).clip(lower=0)
        surplus_kWh = surplus_series.sum()

        # Value of self-consumption = saved (spot price + grid tariff)
        # If you have 'norges-pris' the power-price is capped at e.g. 0.4 NOK/kWh
        if norges_pris:
            consumption_power_price = norges_pris
        else:
            consumption_power_price = spot_price_hourly
        consumption_power_price = (consumption_power_price + grid_tariff) * 1.25  # (25% vat)
        saved_self_consumption_NOK = (self_consumption_series * consumption_power_price).sum()

        # Value of surplus sales = spot price
        sales_NOK = (surplus_series * spot_price_hourly).sum()

        # Total revenue for the year
        yearly_income = saved_self_consumption_NOK + sales_NOK

        # Add to cumulative totals
        inflation_adjustment = (1 + inflation) ** (year - 1)
        cumulative_cashflow += yearly_income * inflation_adjustment

        # Check simple payback (not accounting for interest)
        if payback_years is None and cumulative_cashflow >= investment_cost:
            payback_years = year

        results.append(
            {
                "Year": year,
                "Production (kWh)": yearly_production.sum(),
                "Self-consumption (kWh)": self_consumption_kWh,
                "Exported (kWh)": surplus_kWh,
                "Income (NOK)": yearly_income,
                "Cumulative (NOK)": cumulative_cashflow,
            }
        )

    results_df = pd.DataFrame(results)

    return {
        "results": results_df,
        "total_profit": cumulative_cashflow - investment_cost,
        "payback_period_years": payback_years,
    }


def read_power_price():
    """
    Reads power price data from 'spotpriser.xlsx'.
    Converts the date strings to datetime and sets it as index.
    Returns a Series with power prices indexed by datetime.
    """
    # Read the Excel file
    df = pd.read_excel("spotpriser.xlsx")

    # Convert the date-time strings to datetime objects
    df["date"] = df["Dato/klokkeslett"].str.replace(r"[Kk][Ll]\.|\-|\s+", "", regex=True)
    # Discard the last two characters before conversion
    df["date"] = pd.to_datetime(df["date"].str[:-2], format="%Y%m%d%H")

    # Set the datetime column as index and select the price column
    price_series = df.set_index("date")["NO1"]

    return price_series


def extract_consumption():
    fn = "~/Downloads/consumptionPerGroupMbaHour-en-csv-2022-08-01-to-2025-08-01/part-00000-6b70ae5b-8343-46a4-a6e4-28c1053d2d86-c000.csv"
    df = pd.read_csv(fn)
    df = df[(df["PRICE_AREA"] == "NO1") & (df["CONSUMPTION_GROUP"] == "household")]
    # Convert timestamp to datetime and set as index
    df = df.set_index(pd.to_datetime(df["START_TIME"], utc=True))
    df = df["QUANTITY_KWH"]
    df.to_csv("consumption.csv")  # Save to CSV for later use
    return df


def read_consumption(year: str = "2022", total: float = 25_000):
    """Average household consumption in kWh"""
    df = pd.read_csv("consumption.csv")
    # df["date"] = pd.to_datetime(df["START_TIME"], utc=True)
    df.set_index(pd.to_datetime(df["START_TIME"], utc=True), inplace=True)
    df = df.loc[year]["QUANTITY_KWH"]
    # Normalize to match the total consumption requested
    df = df * (total / df.sum())

    # drop the timezone information
    df.index = df.index.tz_localize(None)

    return df


def read_production(year: str = "2020", yearly_average: float = 23_000):
    """
    Reads solar production data from Excel file and converts it to a time series.
    Returns a pandas Series with hourly production values (kWh) indexed by datetime.

    Parameters:
    -----------
    year : str, default "2020"
        Year to use for the datetime index
    yearly_average: Yearly average prpoduction in kWh
    """
    fn = "/home/u54671/Documents/strøm_pris/GSA_Report_Utveien 27, 1433 Ås, Norway.xlsx"

    # Read the Excel file containing hourly production profiles
    df = pd.read_excel(fn, sheet_name="Hourly_profiles", skiprows=4, nrows=24, usecols=range(1, 13))

    # Assuming the data has hours as rows and months/days as columns
    # Restructure the data into a single time series

    # Get hourly profiles for a typical day of each month
    monthly_profiles = {}
    for month in range(12):  # 1-12 months
        month_profile = []
        for hour in range(24):  # 0-23 hours
            value = df.iloc[hour, month]
            month_profile.append(value)

        # Store the 24-hour profile for this month
        monthly_profiles[month] = month_profile

    # Create a time series for the full year by repeating the daily profile for each day of the month
    full_year_idx = pd.date_range(f"{year}-01-01", f"{int(year) + 1}-01-01", freq="h", inclusive="left")
    production_values = []

    for timestamp in full_year_idx:
        month = timestamp.month
        hour = timestamp.hour

        # Repeat the same daily profile for all days in the month
        value = monthly_profiles[month - 1][hour]
        production_values.append(value)

    # Create a Series from the collected data
    series = pd.Series(production_values, index=full_year_idx)

    return series / series.sum() * yearly_average


def total_investment_cost(
    investment_amount: float, annual_interest_rate: float, loan_years: int
) -> tuple[float, float]:
    """
    Calculate the total cost of an investment when financed by a loan.

    Parameters
    ----------
    investment_amount : float
        The principal loan amount (NOK).
    annual_interest_rate : float
        Annual interest rate (decimal), e.g., 0.04 for 4%.
    loan_years : int
        Duration of loan in years.

    Returns
    -------
        investment_cost, total_interest

    Notes
    -----
    The formula used for fixed monthly payments is the standard annuity loan formula:

        M = (P * r) / (1 - (1 + r)^(-n))

    Where:
        M = fixed monthly payment
        P = principal loan amount (investment_amount)
        r = monthly interest rate = annual_interest_rate / 12
        n = total number of monthly payments = loan_years * 12

    Explanation:
    - The numerator (P * r) represents the interest portion for the current balance
      in the first month.
    - The denominator (1 - (1 + r)^(-n)) adjusts for the fact that the loan is paid
      over multiple months, not all at once.
    - This formula comes from rearranging the present value of an annuity equation.

    Special Case:
    If interest rate is 0% (r = 0), the payment is simply:
        M = P / n
    """
    monthly_rate = annual_interest_rate / 12
    num_payments = loan_years * 12

    monthly_payment = (investment_amount * monthly_rate) / (1 - (1 + monthly_rate) ** -num_payments)

    total_payment = monthly_payment * num_payments
    total_interest = total_payment - investment_amount

    return total_payment, total_interest


def compare_actual_consumption_to_average():
    actual_consumption_per_month = [
        2000,
        1700,
        1650,
        1250,
        1000,
        900,
        850,
        900,
        900,
        1100,
        1700,
        1850,
    ]
    # Read consumption data for both years
    avg_consumption_2023 = read_consumption(total=16_000, year="2023")
    avg_consumption_2024 = read_consumption(total=16_000, year="2024")
    avg_consumption = (
        avg_consumption_2023.resample("ME").sum().values + avg_consumption_2024.resample("ME").sum().values
    ) / 2

    fig, ax = plt.subplots()
    ax.plot(
        avg_consumption,
        label="average household consumption",
    )
    ax.plot(actual_consumption_per_month, label="Actual consumption per month")
    ax.legend()

    adoption_factor = actual_consumption_per_month / avg_consumption

    return adoption_factor


def apparent_adoption_factor(adoption_factor, year):
    date_range = pd.date_range(f"{year}-01-01", f"{int(year) + 1}-01-01", freq="MS", inclusive="both")
    series = pd.DataFrame(np.append(adoption_factor, np.nan), index=date_range)
    series = series.resample("h").ffill()
    series = series.loc[year]
    return series


# -------------------------
# Example usage
# -------------------------
if __name__ == "__main__":
    consume_adoption_factor_org = compare_actual_consumption_to_average()

    results = []
    loan_years = 20

    for norges_pris in [False, 0.4]:
        print("\nNorges-pris:", norges_pris)
        # Note data is only complete for the year 2023, 2024
        for year in ["2023", "2024"]:
            print(f"Calculating for year: {year}")
            for consume_adoption_factor in [True, False]:
                if consume_adoption_factor:
                    adoption_factor = apparent_adoption_factor(adoption_factor=consume_adoption_factor_org, year=year)
                    adoption_factor = adoption_factor.to_numpy().squeeze()
                else:
                    adoption_factor = 1

                # Production: more during daytime, zero at night
                production = read_production(year)

                # Spot price: constant for simplicity (NOK/kWh)
                spot_price = read_power_price().loc[year]

                # Consumption: constant
                # consumption = extract_consumption()
                consumption = read_consumption(year, total=16_000) * adoption_factor

                # total_cost, total_interrest = 300_000, 3e5 - 265_000
                total_cost, total_interrest = total_investment_cost(
                    investment_amount=265_000,
                    annual_interest_rate=0.05,
                    loan_years=loan_years,
                )

                result = calculate_solar_economics(
                    production_hourly=production,
                    spot_price_hourly=spot_price,
                    consumption_hourly=consumption,
                    investment_cost=total_cost,
                    lifetime_years=35,
                    degradation_per_year=0.005,  # 0.5%
                    grid_tariff=0.5,  # NOK/kWh
                    system_losses=0.12,
                    norges_pris=norges_pris,
                )

                # print(result["results"])

                print("Sanity checks:")
                print(f"Yearly production: {round(production.sum())} kWh")
                print(f"Yearly consumption: {round(consumption.sum())} kWh")
                print(f"Average spot price: {spot_price.mean():.2f} NOK/kWh")
                print("")
                print(
                    "Total investment cost: "
                    f"{round(total_cost, 2):,} NOK (including {round(total_interrest, 2):,} NOK interest)"
                )

                print(f"Payback period: {result['payback_period_years']} years")
                results.append(
                    [
                        consume_adoption_factor,
                        norges_pris,
                        year,
                        round(result["total_profit"]),
                        result["payback_period_years"],
                    ]
                )
    # Convert results to a DataFrame and print
    results_df = pd.DataFrame(
        results,
        columns=[
            "consume_adoption_factor",
            "norges_pris",
            "year",
            "total_profit",
            "payback_period_years",
        ],
    )
    print(results_df)
    plt.show()

    # fig, ax = plt.subplots(2, 1)
    # production.plot(ax=ax[0], label="Production")
    # consumption.plot(ax=ax[0], label="Consumption")
    # spot_price.plot(ax=ax[1], label="Spot Price")
    # ax[0].legend()
    # ax[1].legend()
    # plt.show()
