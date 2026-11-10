# Sources and Third-Party Components

OCULUS is built on the components below. Each keeps its own licence. The project's own [LICENSE](LICENSE) covers only the author's code and does not change any of these licences.

## Dataset

| Dataset | Author | Licence | Used for |
|---|---|---|---|
| [plaka_okuma, version 1](https://universe.roboflow.com/kemal-m9bea/plaka_okuma/dataset/1) (Roboflow Universe) | kemal-m9bea | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Training the licence plate detector |

**Attribution (CC BY 4.0):** The plate detector (`models/plate_1.pt`) was trained on *plaka_okuma*, by kemal-m9bea, from Roboflow Universe, licensed under CC BY 4.0.

**Changes made:** the dataset was used to fine-tune YOLOv8s for 50 epochs. The dataset itself was not modified or redistributed. On its validation split the resulting detector scores mAP50 0.991, mAP50-95 0.862, precision 0.983 and recall 0.960.

## Models

| Model | Source | Licence | Used for |
|---|---|---|---|
| YOLOv8s (`yolov8s.pt`), COCO-pretrained | [Ultralytics](https://github.com/ultralytics/ultralytics) | AGPL-3.0 | Vehicle detection (car, motorcycle, bus, truck), and the base model for the plate detector |
| `plate_1.pt` (own) | YOLOv8s fine-tuned on the dataset above | Derived from YOLOv8s (AGPL-3.0) and the dataset (CC BY 4.0) | Licence plate detection |
| `cct-s-v2-global-model` | [fast-plate-ocr](https://github.com/ankandrew/fast-plate-ocr) | MIT | Plate character recognition (OCR) |

Model weights (`*.pt`) are not included in the repository.

## Libraries

| Library | Version | Licence | Used for |
|---|---|---|---|
| [Ultralytics](https://github.com/ultralytics/ultralytics) | 8.4 | AGPL-3.0 | YOLOv8 detection, training, and tracking |
| [BoT-SORT](https://github.com/NirAharon/BoT-SORT) (built into Ultralytics) | — | MIT | Multi-object tracking of vehicles |
| [fast-plate-ocr](https://github.com/ankandrew/fast-plate-ocr) | 1.1 | MIT | Plate OCR |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | 1.31 | MIT | Running the OCR model |
| [PyTorch](https://github.com/pytorch/pytorch) | 2.11 | BSD-3-Clause | Backend for YOLO |
| [OpenCV](https://github.com/opencv/opencv-python) | 5.0 | Apache-2.0 | Video input and image processing |
| [NumPy](https://github.com/numpy/numpy) | 2.5 | BSD-3-Clause | Arrays |
| [PySide6 (Qt for Python)](https://doc.qt.io/qtforpython-6/) | 6.12 | LGPL-3.0 | Desktop user interface |

### Used only for comparison

| Library | Licence | Used for |
|---|---|---|
| [EasyOCR](https://github.com/JaidedAI/EasyOCR) | Apache-2.0 | Phase 0 OCR baseline (14% of plates read correctly), replaced by fast-plate-ocr |

## References

- Jocher, G., Chaurasia, A., & Qiu, J. (2023). *Ultralytics YOLOv8* (Version 8.0.0). https://github.com/ultralytics/ultralytics
- Aharon, N., Orfaig, R., & Bobrovsky, B.-Z. (2022). *BoT-SORT: Robust Associations Multi-Pedestrian Tracking*. arXiv:2206.14651. https://arxiv.org/abs/2206.14651
- Lin, T.-Y., et al. (2014). *Microsoft COCO: Common Objects in Context*. ECCV 2014. https://cocodataset.org (the dataset YOLOv8s was pretrained on)
- kemal-m9bea. *plaka_okuma Dataset* (Version 1). Roboflow Universe. https://universe.roboflow.com/kemal-m9bea/plaka_okuma/dataset/1
- ankandrew. *fast-plate-ocr*. https://github.com/ankandrew/fast-plate-ocr
