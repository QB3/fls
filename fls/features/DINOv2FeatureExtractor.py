import torch
import torchvision.transforms as transforms
from fls.features.FeatureExtractor import FeatureExtractor


class DINOv2FeatureExtractor(FeatureExtractor):
    def __init__(self, recompute=False, save_path=None):
        self.name = f"dinov2"
        super().__init__(recompute=recompute, save_path=save_path)

        self.features_size = 768
        # From https://github.com/facebookresearch/dinov2/blob/main/dinov2/data/transforms.py#L44
        self.preprocess = transforms.Compose(
            [
                transforms.Resize(
                    (224, 224), interpolation=transforms.InterpolationMode.BICUBIC
                ),
                transforms.CenterCrop(224),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)
                ),
            ]
        )

        # self.model = torch.hub.load("facebookresearch/dinov2", "dinov2_vitl14")
        self.model = torch.hub.load("facebookresearch/dinov2", "dinov2_vitb14")
        self.model.eval()
        self.model.to("cuda")

    def preprocess_batch(self, img_batch):
        return self.preprocess(img_batch)

    def get_feature_batch(self, img_batch):
        with torch.no_grad():
            embeddings = self.model(img_batch)
        return embeddings
