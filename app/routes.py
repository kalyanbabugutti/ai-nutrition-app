import shutil
import os
from fastapi import APIRouter, Request, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from .model import predict_image

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Nutrition data (no database) - per typical serving
NUTRITION_DATA = {
    "Banana": {"calories": 89, "protein": 1.1, "carbs": 23, "fat": 0.3},
    "Apple": {"calories": 52, "protein": 0.3, "carbs": 14, "fat": 0.2},
    "Pizza": {"calories": 266, "protein": 11, "carbs": 33, "fat": 10},
    "Cheeseburger": {"calories": 295, "protein": 17, "carbs": 30, "fat": 14},
    "Hotdog": {"calories": 290, "protein": 11, "carbs": 4, "fat": 26},
    "Orange": {"calories": 47, "protein": 0.9, "carbs": 12, "fat": 0.1},
    "Broccoli": {"calories": 55, "protein": 3.7, "carbs": 11, "fat": 0.6},
    "Carrot": {"calories": 41, "protein": 0.9, "carbs": 10, "fat": 0.2},
    "Strawberry": {"calories": 33, "protein": 0.7, "carbs": 8, "fat": 0.3},
    "Lemon": {"calories": 17, "protein": 0.6, "carbs": 5, "fat": 0.2},
    "Pineapple": {"calories": 82, "protein": 0.9, "carbs": 22, "fat": 0.2},
    "Mushroom": {"calories": 15, "protein": 2.2, "carbs": 2.3, "fat": 0.2},
    "Bell Pepper": {"calories": 30, "protein": 1.4, "carbs": 7, "fat": 0.2},
    "Cabbage": {"calories": 22, "protein": 1.1, "carbs": 5, "fat": 0.1},
    "Cauliflower": {"calories": 25, "protein": 2, "carbs": 5, "fat": 0.1},
    "Cucumber": {"calories": 8, "protein": 0.3, "carbs": 2, "fat": 0.1},
    "Lettuce": {"calories": 5, "protein": 0.5, "carbs": 1, "fat": 0.1},
    "Burrito": {"calories": 206, "protein": 8, "carbs": 27, "fat": 7},
    "Sandwich": {"calories": 250, "protein": 12, "carbs": 28, "fat": 10},
    "Burger": {"calories": 354, "protein": 17, "carbs": 30, "fat": 14},
    "Ice Cream": {"calories": 140, "protein": 2.5, "carbs": 16, "fat": 7},
    "Pie": {"calories": 300, "protein": 4, "carbs": 40, "fat": 14},
    # Indian foods
    "Dal": {"calories": 115, "protein": 8, "carbs": 20, "fat": 1},
    "Rice": {"calories": 130, "protein": 2.7, "carbs": 28, "fat": 0.3},
    "Biryani": {"calories": 350, "protein": 12, "carbs": 45, "fat": 12},
    "Samosa": {"calories": 262, "protein": 4.2, "carbs": 31, "fat": 14},
    "Naan": {"calories": 262, "protein": 9, "carbs": 46, "fat": 5},
    "Roti": {"calories": 104, "protein": 3, "carbs": 22, "fat": 0.5},
    "Paratha": {"calories": 326, "protein": 10, "carbs": 46, "fat": 12},
    "Curry": {"calories": 180, "protein": 8, "carbs": 12, "fat": 11},
    "Idli": {"calories": 58, "protein": 2.2, "carbs": 12, "fat": 0.4},
    "Dosa": {"calories": 133, "protein": 3.7, "carbs": 26, "fat": 1.2},
    "Chole": {"calories": 210, "protein": 11, "carbs": 35, "fat": 4},
    "Rajma": {"calories": 127, "protein": 8.7, "carbs": 23, "fat": 0.5},
    "Paneer": {"calories": 265, "protein": 18, "carbs": 4, "fat": 20},
    "Aloo Gobi": {"calories": 120, "protein": 3, "carbs": 18, "fat": 4},
    "Pakora": {"calories": 180, "protein": 5, "carbs": 22, "fat": 8},
    "Kheer": {"calories": 250, "protein": 6, "carbs": 42, "fat": 6},
    "Gulab Jamun": {"calories": 150, "protein": 2.5, "carbs": 22, "fat": 6},
}

# Map ResNet/ImageNet prediction (lowercase, partial match) -> NUTRITION_DATA key
FOOD_MAPPING = {
    "banana": "Banana",
    "granny_smith": "Apple",
    "apple": "Apple",
    "pizza": "Pizza",
    "cheeseburger": "Cheeseburger",
    "hotdog": "Hotdog",
    "hot dog": "Hotdog",
    "orange": "Orange",
    "broccoli": "Broccoli",
    "carrot": "Carrot",
    "strawberry": "Strawberry",
    "lemon": "Lemon",
    "pineapple": "Pineapple",
    "mushroom": "Mushroom",
    "bell_pepper": "Bell Pepper",
    "pepper": "Bell Pepper",
    "cabbage": "Cabbage",
    "cauliflower": "Cauliflower",
    "cucumber": "Cucumber",
    "lettuce": "Lettuce",
    "burrito": "Burrito",
    "sandwich": "Sandwich",
    "burger": "Burger",
    "ice cream": "Ice Cream",
    "pie": "Pie",
    # Indian food mappings (ImageNet classes that may match)
    "dumpling": "Samosa",
    "hot pot": "Curry",
    "mashed potato": "Aloo Gobi",
    "potato": "Aloo Gobi",
    "plate": "Biryani",
    "soup": "Dal",
    "bagel": "Naan",
    "pretzel": "Naan",
    "bread": "Naan",
    "trifle": "Kheer",
    "meat loaf": "Paneer",
    "guacamole": "Chole",
    "bean": "Rajma",
    "pea": "Chole",
}

# Junk / processed foods - get low health score
JUNK_FOODS = {
    "Cheeseburger", "Burger", "Hotdog", "Pizza", "Pie", "Ice Cream",
    "Gulab Jamun", "Pakora", "Samosa", "Paratha", "Biryani",
}


def calculate_health_score(calories, protein, fat, food_name=None):
    if food_name and food_name in JUNK_FOODS:
        return min(45, 100 - (calories // 10) - (fat * 2))
    score = 100
    if calories > 300:
        score -= 20
    if fat > 20:
        score -= 15
    if protein < 5:
        score -= 10
    return max(0, score)


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/analyze", response_class=HTMLResponse)
def analyze_page(request: Request):
    return templates.TemplateResponse("analyze.html", {"request": request})


UPLOAD_DIR = "static/uploads"


@router.post("/analyze", response_class=HTMLResponse)
def analyze(request: Request, file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = os.path.basename(file.filename) or "image.jpg"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    prediction = predict_image(file_path).lower()
    print("PREDICTED:", prediction)

    matched_food = None
    for key in sorted(FOOD_MAPPING.keys(), key=len, reverse=True):
        if key in prediction:
            matched_food = FOOD_MAPPING[key]
            break

    if not matched_food:
        return templates.TemplateResponse(
            "result.html",
            {"request": request, "error": "Food not recognized."},
        )

    data = NUTRITION_DATA[matched_food]

    calories = data["calories"]
    protein = data["protein"]
    carbs = data["carbs"]
    fat = data["fat"]

    score = calculate_health_score(calories, protein, fat, matched_food)
    is_junk = matched_food in JUNK_FOODS

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "image": f"uploads/{safe_name}",
            "food": matched_food,
            "calories": calories,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
            "score": score,
            "is_junk": is_junk,
        },
    )