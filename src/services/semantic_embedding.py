"""Multilingual E5 encoder for the versioned Qdrant index."""
import torch
from torch.nn import functional as F


class E5Encoder:
    model_id = "intfloat/multilingual-e5-base"
    revision = "d128750597153bb5987e10b1c3493a34e5a4502a"
    identifier = model_id + "@" + revision
    dimension = 768

    def __init__(self):
        from transformers import AutoModel, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id, revision=self.revision)
        self.model = AutoModel.from_pretrained(self.model_id, revision=self.revision, use_safetensors=True).eval()

    @torch.inference_mode()
    def encode(self, texts, prefix):
        vectors = []
        for start in range(0, len(texts), 8):
            inputs = self.tokenizer(
                [prefix + text for text in texts[start:start + 8]],
                max_length=512, padding=True, truncation=True, return_tensors="pt",
            )
            hidden = self.model(**inputs).last_hidden_state
            mask = inputs.attention_mask.unsqueeze(-1)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1)
            vectors.extend(F.normalize(pooled, p=2, dim=1).tolist())
        return vectors

    def passages(self, texts):
        return self.encode(texts, "passage: ")

    def query(self, text):
        return self.encode([text], "query: ")[0]
