from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


class FarmCalendarView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Example logic for farm calendar
        return Response({"message": "Farm calendar data"})


