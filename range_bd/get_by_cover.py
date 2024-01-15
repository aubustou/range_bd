from __future__ import annotations

import argparse
import logging
from pathlib import Path

import torch
from PIL import Image
from torchvision import models, transforms

logger = logging.getLogger(__name__)

FOLDER = Path(r"M:\Bédés\thumbnails")


def init() -> tuple[torch.nn.Module, transforms.Compose]:
    # Charger le modèle pré-entraîné (ResNet dans cet exemple)
    model = models.resnet50(pretrained=True)
    model.eval()  # Mettre le modèle en mode évaluation

    # Transformer pour prétraiter les images
    preprocess = transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    return model, preprocess


def extract_features(
    model: torch.nn.Module, preprocess: transforms.Compose, image_path: Path
):
    logger.info("Extracting features from %s", image_path)
    image = Image.open(str(image_path)).convert("RGB")
    image = preprocess(image)
    image = image.unsqueeze(0)  # Ajouter une dimension de batch

    # Pas de calcul de gradient nécessaire
    with torch.no_grad():
        # Obtenir les caractéristiques de l'image
        features = model(image)

    return features


IMG_FILETYPES = {".png", ".jpg", ".gif"}


def recurse(
    model: torch.nn.Module,
    preprocess: transforms.Compose,
    top_path: Path,
    features: list[torch.Tensor],
):
    for subpath in top_path.iterdir():
        if subpath.is_dir():
            recurse(model, preprocess, subpath, features)
        elif subpath.suffix.lower() in IMG_FILETYPES:
            try:
                features_ = extract_features(model, preprocess, subpath)
            except Exception as exc:
                logger.exception(exc)
            else:
                features.append(features_)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path, default=FOLDER, nargs="?")
    args = parser.parse_args()

    folder = args.folder
    if not folder.is_dir():
        parser.error(f"{folder} is not a directory")

    logging.basicConfig(level=logging.INFO)

    model, preprocess = init()
    features_list = []

    recurse(model, preprocess, folder, features_list)

    # features_list contient maintenant les caractéristiques des images du répertoire A

    with open(folder / "features.json", "wb") as f:
        torch.save(features_list, f)


if __name__ == "__main__":
    main()
