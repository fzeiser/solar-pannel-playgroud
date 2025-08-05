import numpy as np
import pandas as pd
from matplotlib import pyplot as plt


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
    fn = "/home/u54671/Documents/strøm_pris/GSA_Report_Ås_Norway.xlsx"

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

