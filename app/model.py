import torch
from PIL import Image
from torchvision.models import resnet18, ResNet18_Weights

device = torch.device("cpu")

# Build model architecture
model = resnet18(weights=None)

# Load pre-downloaded weights
model.load_state_dict(
    torch.load("models/resnet18_weights.pth", map_location=device)
)

model.eval()
model.to(device)

# Get ImageNet labels + transforms
weights_meta = ResNet18_Weights.DEFAULT
imagenet_classes = weights_meta.meta["categories"]
transform = weights_meta.transforms()


def predict_image(image_path: str):
    image = Image.open(image_path).convert("RGB")
    image = transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        outputs = model(image)
        _, predicted = torch.max(outputs, 1)

    return imagenet_classes[predicted.item()]