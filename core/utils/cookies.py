from django.conf import settings


REFRESH_COOKIE_KEY = "refresh"
REFRESH_COOKIE_PATH = "/v1/auth/"
REFRESH_COOKIE_MAX_AGE = 7 * 24 * 60 * 60


def set_refresh_cookie(response, refresh_token):
    response.set_cookie(
        key=REFRESH_COOKIE_KEY,
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Strict",
        path=REFRESH_COOKIE_PATH,
        max_age=REFRESH_COOKIE_MAX_AGE,
    )


def unset_refresh_cookie(response):
    response.delete_cookie(REFRESH_COOKIE_KEY, path=REFRESH_COOKIE_PATH)
