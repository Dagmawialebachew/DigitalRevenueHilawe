from .onboarding import router as onboarding
from .payment import router as payment
from .dashboard import router as dashboard
from .admin import router as admin
# from .fallback import router as fallback

# The order here is critical for the Dispatcher
all_routers = [
    admin,       # Admin first (highest priority)
    onboarding,
    payment,
    dashboard
]