# //===------DailyVision-src\ocr.py-----------------------------------------===//
# // Part of the Startup-Demos Project, under the MIT License
# // See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# // for license information.
# // Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# // SPDX-License-Identifier: MIT License
# // Project done by - Vishnudatta (vindraga@qti.qualcomm.com)
# //===----------------------------------------------------------------------===//

from PIL import Image
import cv2
import numpy as np
from qai_hub_models.models.easyocr.app import EasyOCRApp
from qai_hub_models.models.easyocr.model import MODEL_ID, EasyOCR
from qai_hub_models.utils.args import (
    get_model_cli_parser,
    get_on_device_demo_parser,
    model_from_cli_args,
    validate_on_device_demo_args,
)

def perform_ocr(image_path):
    parser = get_model_cli_parser(EasyOCR)
    parser = get_on_device_demo_parser(parser, add_output_dir=True)
    parser.add_argument("--image", type=str, default=image_path, help="image file path or URL")
    args = parser.parse_args([])

    validate_on_device_demo_args(args, MODEL_ID)
    ocr_model = model_from_cli_args(EasyOCR, args)
    ocr_app = EasyOCRApp(ocr_model.detector, ocr_model.recognizer, ocr_model.lang_list)

    image = cv2.imread(image_path)
    pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    ocr_results = ocr_app.predict_text_from_image(cv_image)

    texts = [text for _, text, _ in ocr_results[1]]
    return " ".join(texts)
