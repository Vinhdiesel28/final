"""CPU inference wrapper; preprocessing is fitted exclusively on train."""
import numpy as np
import torch
from torch import nn


class RiskMLP(nn.Module):
    def __init__(self, inputs):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(inputs, 64), nn.ReLU(), nn.Dropout(.15),
                                 nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, x):
        return self.net(x).squeeze(-1)


class TorchPipeline:
    def __init__(self, checkpoint, preprocess):
        torch.set_num_threads(2)
        saved = torch.load(checkpoint, map_location='cpu', weights_only=True)
        self.model = RiskMLP(saved['input_dim'])
        self.model.load_state_dict(saved['state_dict'])
        self.model.eval()
        self.preprocess = preprocess

    def predict_proba(self, frame):
        x = torch.as_tensor(self.preprocess.transform(frame), dtype=torch.float32)
        with torch.inference_mode():
            p = torch.sigmoid(self.model(x)).numpy()
        return np.column_stack([1-p, p])
