from ultralytics import YOLO

model = YOLO("yolov8n.pt")

model.train(
    data="ecorefill_dataset/data.yaml",
    epochs=50,
    imgsz=640,
    batch=8,
    name="ecorefill_yolo_model"
)