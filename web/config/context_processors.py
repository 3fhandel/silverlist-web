from django.conf import settings


def build_info(request):
    return {"silverlists_build": settings.SILVERLISTS_BUILD}
