from django.shortcuts import render,redirect
from django.contrib import messages
import pandas as pd
import os
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from geopy.distance import geodesic
from django.http import JsonResponse
import json
from .route_engine import get_crime_aware_route

from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")





def google_route_view(request):
    return render(request, 'crimeapp/google_route.html', {
        'google_api_key': GOOGLE_API_KEY,
        'center_lat': 41.8781,
        'center_lon': -87.6298
    })


@csrf_exempt
def get_custom_route(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            origin = data.get("origin")
            destination = data.get("destination")

            if not origin or not destination:
                return JsonResponse({
                    "ok": False,
                    "code": "MISSING_POINTS",
                    "message": "Please select both a start and destination point."
                }, status=400)

            try:
                result = get_crime_aware_route(
                    origin_lat=origin["lat"],
                    origin_lng=origin["lng"],
                    dest_lat=destination["lat"],
                    dest_lng=destination["lng"]
                )
            except ValueError as ve:
                # Suppose your route engine raises ValueError for out-of-bounds nodes
                return JsonResponse({
                    "ok": False,
                    "code": "OUT_OF_BOUNDS",
                    "message": str(ve) or "Selected points are outside the supported Chicago area."
                }, status=400)
            except RuntimeError as re:
                # No path between nodes
                return JsonResponse({
                    "ok": False,
                    "code": "NO_PATH",
                    "message": "No safe path could be found between the selected locations."
                }, status=404)

            return JsonResponse({
                "ok": True,
                "route": result["route"],
                "safety_info": result["safety_info"]
            }, status=200)

        except Exception as e:
            return JsonResponse({
                "ok": False,
                "code": "SERVER_ERROR",
                "message": "Unexpected server error: " + str(e)
            }, status=500)

    return JsonResponse({
        "ok": False,
        "code": "METHOD_NOT_ALLOWED",
        "message": "Only POST requests are allowed."
    }, status=405)


def about(request):
    return render(request, "crimeapp/about.html")

def disclaimer(request):
    return render(request, "crimeapp/disclaimer.html")

def help(request):
    return render(request, "crimeapp/help.html")

def contact(request):
    if request.method == "POST":
        # simple honeypot
        if request.POST.get("website"):
            return redirect("contact")

        email = (request.POST.get("email") or "").strip()
        subject = (request.POST.get("subject") or "").strip()
        message_body = (request.POST.get("message") or "").strip()

        errors = []
        if not email:
            errors.append("Email is required.")
        if not message_body:
            errors.append("Message is required.")

        if errors:
            return render(request, "crimeapp/contact.html", {
                "errors": errors,
                "form": {"email": email, "subject": subject, "message": message_body},
            })

        # For now, just log it to the console (safe default without email setup)
        print("\n===== CONTACT MESSAGE =====")
        print(f"From: {email}")
        print(f"Subject: {subject}")
        print(f"Message:\n{message_body}")
        print("==========================\n")

        messages.success(request, "Thanks! Your message has been sent.")
        return redirect("contact")

    return render(request, "crimeapp/contact.html")

def privacy(request):
    return render(request, "crimeapp/privacy.html")

def terms(request):
    return render(request, "crimeapp/terms.html")










