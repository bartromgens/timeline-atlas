from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def auth_me(request):
    if request.user.is_authenticated:
        return Response(status=200)
    return Response(status=401)
