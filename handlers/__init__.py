from .onboarding import router as onboarding
from .payment import router as payment
from .dashboard import router as dashboard
from .admin import router as admin
from .verify import router as verify
# from .fallback import router as fallback

# The order here is critical for the Dispatcher
all_routers = [
    admin,       # Admin first (highest priority)
    verify,
    onboarding,
    dashboard,
    payment,
]