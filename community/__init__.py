from .club_billing import router as club_billing
from .club_promo import router as club_promo
from .club_renewal import router as club_renewal

# from .fallback import router as fallback

# The order here is critical for the Dispatcher
all_comm_routers = [
    club_billing,
    club_promo,
    club_renewal,
]