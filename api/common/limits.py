import os

# Energy — global daily guess budget across all games
ENERGY_DAILY_ANONYMOUS  = int(os.getenv("ENERGY_DAILY_ANONYMOUS",   10))
ENERGY_DAILY_GUEST      = int(os.getenv("ENERGY_DAILY_GUEST",       15))
ENERGY_DAILY_USER       = int(os.getenv("ENERGY_DAILY_USER",        30))
ENERGY_DAILY_SUBSCRIBER = int(os.getenv("ENERGY_DAILY_SUBSCRIBER", 250))
ENERGY_MAX_SUBSCRIBER   = int(os.getenv("ENERGY_MAX_SUBSCRIBER",   250))
