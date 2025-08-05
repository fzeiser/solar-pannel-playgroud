# Solar Panel Playground

**Playground** to calculate the revenue from installing solar panels. 

The code has not been optimized, but was created as a mini project in support of a private investment decision.

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/fzeiser/solar-pannel-playgroud/main?filepath=solar_production_demo.ipynb)

## Overview

This repository contains tools to roughly analyze the financial performance of residential solar panel installations. It includes:

- Solar production modeling and estimation
- Economic calculations for investment analysis
- Example data for electricity consumption and spot prices

## Why should I bother to create a code around this?

The calculations take into account hourly fluctuations and realistic spot-price, consumptions data etc. for Ås, Norway. Most other
calculations are based on average power-prices, but we know that power-prices are usually considerably lower duing the night 
than during the day. In addition, we wanted to separate between self-consumption, and excess power. For the former, we also pay
a grid_tariff.


## Getting Started

### Launch with Binder

The easiest way to explore this code is by launching it on Binder - just click the badge above.

## Project Structure

- `solar_production.py`: Main module with economic calculation functions
- `consumption.csv`: Example electricity consumption data
- `spotpriser.xlsx`: Example electricity spot prices
