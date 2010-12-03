from django.conf import settings
from django.utils.importlib import import_module
from django.core.exceptions import ImproperlyConfigured

from tardis.tardis_portal.auth.interfaces import AuthProvider, UserProvider, GroupProvider


class AuthService:
    def __init__(self, settings=settings):
        self._group_providers = []
        self._user_providers = []

        for gp in settings.GROUP_PROVIDERS:
            self._group_providers.append(self._safe_import(gp))
        for up in settings.USER_PROVIDERS:
            self._user_providers.append(self._safe_import(up))

    def _safe_import(self, path):
        try:
            dot = path.rindex('.')
        except ValueError:
            raise ImproperlyConfigured('%s isn\'t a middleware module' % path)
        auth_module, auth_classname = path[:dot], path[dot + 1:]
        try:
            mod = import_module(auth_module)
        except ImportError, e:
            raise ImproperlyConfigured('Error importing auth module %s: "%s"' %
                                       (auth_module, e))
        try:
            auth_class = getattr(mod, auth_classname)
        except AttributeError:
            raise ImproperlyConfigured('Auth module "%s" does not define a "%s" class' %
                                       (auth_module, auth_classname))

        auth_instance = auth_class()
        return auth_instance

    def authenticate(self, request):
        """
        Try and authenticate the user first using Django auth backends,
        then try each AuthProvider.
        """
        pass

    def getGroups(self, request):
        """
        return a list of tuples containing pluginname and group id
        """
        for gp in self._group_providers:
            for group in gp.getGroups(request):
                yield (gp.name, group)

    def searchEntities(self, filter):
        """
        return a list of users and/or groups
        """
        pass

    def searchUsers(self, filter):
        """
        return a list of users and/or groups
        """
        pass

    def searchGroups(self, filter):
        """
        return a list of users and/or groups
        """
        pass

    def getGroupsForEntity(self, entity):
        """
        Look in UserAuthentation, pull auth sources and query approprate
        auth plugins.
        """
        pass

    def getUser(self, user_dict):
        """
        return a user model based on the user dict.

        This function is responsible for creating the
        user within the Django DB and returning the resulting
        user model.
        """
        pass

auth_service = AuthService()


class LazyGroups(object):
    def __get__(self, request, obj_type=None):
        if not hasattr(request, '_cached_groups'):
            request._cached_groups = auth_service.getGroups(request)
        return request._cached_groups


class AuthorizationMiddleware(object):
    def process_request(self, request):
        assert hasattr(request, 'session'), "The Django authorization middleware requires session middleware to be installed. Edit your MIDDLEWARE_CLASSES setting to insert 'django.contrib.sessions.middleware.SessionMiddleware'."
        request.__class__.groups = LazyGroups()
        return None
