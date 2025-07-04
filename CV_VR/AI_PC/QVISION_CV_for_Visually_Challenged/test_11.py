from ultralytics import YOLO
import cv2
from PIL import Image
import numpy as np
import pyttsx3
import multiprocessing

from qai_hub_models.models.easyocr.app import EasyOCRApp
from qai_hub_models.models.easyocr.model import MODEL_ASSET_VERSION, MODEL_ID, EasyOCR
from qai_hub_models.utils.args import (
    get_model_cli_parser,
    get_on_device_demo_parser,
    model_from_cli_args,
    validate_on_device_demo_args,
)

def speak_text(text):
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()

def classify_traffic_light(cropped_image):
    # Convert the image to HSV color space
    hsv = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2HSV)

    # Define color ranges for red, yellow, and green in HSV space
    red_lower1 = np.array([0, 100, 100])
    red_upper1 = np.array([10, 255, 255])
    red_lower2 = np.array([160, 100, 100])
    red_upper2 = np.array([180, 255, 255])
    yellow_lower = np.array([15, 100, 100])
    yellow_upper = np.array([35, 255, 255])
    green_lower = np.array([40, 100, 100])
    green_upper = np.array([90, 255, 255])

    # Create masks for red, yellow, and green colors
    mask_red1 = cv2.inRange(hsv, red_lower1, red_upper1)
    mask_red2 = cv2.inRange(hsv, red_lower2, red_upper2)
    mask_red = cv2.bitwise_or(mask_red1, mask_red2)
    mask_yellow = cv2.inRange(hsv, yellow_lower, yellow_upper)
    mask_green = cv2.inRange(hsv, green_lower, green_upper)

    # Calculate the percentage of each color in the image
    red_percentage = np.sum(mask_red) / (cropped_image.shape[0] * cropped_image.shape[1])
    yellow_percentage = np.sum(mask_yellow) / (cropped_image.shape[0] * cropped_image.shape[1])
    green_percentage = np.sum(mask_green) / (cropped_image.shape[0] * cropped_image.shape[1])

    # Determine the color with the highest percentage
    if red_percentage > yellow_percentage and red_percentage > green_percentage:
        return "red"
    elif yellow_percentage > red_percentage and yellow_percentage > green_percentage:
        return "yellow"
    else:
        return "green"

def main():
    # Path to the input image
    image_path = r"C:\Users\vindraga\Downloads\traffic_red.jpg"
    # image_path = r"C:\Users\vindraga\Downloads\signboard_11.jpg"
    # image_path = r"C:\Users\vindraga\Downloads\signboard_9.jpg"
    # image_path = r"C:\Users\vindraga\Downloads\signboard_6.jpg"
    # image_path = r"C:\Users\vindraga\Downloads\signboards\car\test\images\road84_png.rf.3c4a24183c70e3af08fc01ae65761c88.jpg"
    # image_path = r"C:\Users\vindraga\Downloads\signboards\car\test\images\road859_png.rf.f0e4bbd39d237c79817d4ade35676364.jpg"

    yolo_model = YOLO('yolov8l.pt')
    image = cv2.imread(image_path)
    results = yolo_model(image)
    objects_detected = any(len(result.boxes) > 0 for result in results)

    if objects_detected:
        annotated_image = results[0].plot()
        cv2.imwrite("annotated_output.jpg", annotated_image)
        Image.open("annotated_output.jpg").show()
        print("Saved annotated image as annotated_output.jpg")

        parser = get_model_cli_parser(EasyOCR)
        parser = get_on_device_demo_parser(parser, add_output_dir=True)
        parser.add_argument("--image", type=str, default=image_path, help="image file path or URL")
        args = parser.parse_args([])

        validate_on_device_demo_args(args, MODEL_ID)
        ocr_model = model_from_cli_args(EasyOCR, args)
        ocr_app = EasyOCRApp(ocr_model.detector, ocr_model.recognizer, ocr_model.lang_list)

        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cropped = image[y1:y2, x1:x2]

                pil_image = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
                cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                ocr_results = ocr_app.predict_text_from_image(cv_image)
                print(ocr_results)

                texts = [text for _, text, _ in ocr_results[1]]
                combined_text = " ".join(texts)

                label = yolo_model.names[int(box.cls[0])] if hasattr(box, 'cls') else "object"

                if label == "traffic light":
                    traffic_light_color = classify_traffic_light(cropped)
                    spoken_text = f"Detected a {label} with color: {traffic_light_color}"
                else:
                    spoken_text = f"Detected a {label} : {combined_text}"

                print(spoken_text)
                speak_text(spoken_text)
                
    else:
        parser = get_model_cli_parser(EasyOCR)
        parser = get_on_device_demo_parser(parser, add_output_dir=True)
        parser.add_argument("--image", type=str, default=image_path, help="image file path or URL")
        args = parser.parse_args([])

        validate_on_device_demo_args(args, MODEL_ID)
        ocr_model = model_from_cli_args(EasyOCR, args)
        ocr_app = EasyOCRApp(ocr_model.detector, ocr_model.recognizer, ocr_model.lang_list)

        pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

        cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        ocr_results = ocr_app.predict_text_from_image(cv_image)
        print(ocr_results)

        texts = [text for _, text, _ in ocr_results[1]]
        combined_text = " ".join(texts)

        spoken_text = f"Detected text: {combined_text}"
        print(spoken_text)
        speak_text(spoken_text)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
