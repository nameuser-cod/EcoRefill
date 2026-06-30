from ultralytics import YOLO

model = YOLO("models/ecorefill_best.pt")

image_path = input("Enter image path: ")

results = model.predict(
    source=image_path,
    conf=0.5,
    save=True
)

print("Detection finished.")
print("Check the output folder: runs/detect/predict")