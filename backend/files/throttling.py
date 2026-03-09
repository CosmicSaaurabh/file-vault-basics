from rest_framework.throttling import UserRateThrottle, BaseThrottle

class UserIdRateThrottle(UserRateThrottle):
    scope = 'user_id'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            return super().get_cache_key(request, view)
        
        user_id = request.headers.get('UserId')
        if not user_id:
            return None

        return self.cache_format % {
            'scope': self.scope,
            'ident': user_id
        }

# throttling.py (add this class)
class NoThrottle(BaseThrottle):
    def allow_request(self, request, view):
        return True  # always allow
    def wait(self):
        return None
