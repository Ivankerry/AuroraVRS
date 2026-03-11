import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

class TwoTowerModel(nn.Module):
    def __init__(self, tag_vocab: dict[str, int], tag_embeddings: dict = None):
        super().__init__()
        self.tag_vocab = tag_vocab
        self.num_tags = len(tag_vocab)
        self.tag_embeddings = tag_embeddings or {}
        self._build_networks()

    def _build_networks(self):
        # User Tower (Wider & Deeper for multi-modal interests)
        self.user_tower = nn.Sequential(
            nn.Linear(384 + 2, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Linear(256, 128)
        )
        
        # Video Tower (Wider & Deeper)
        self.video_tower = nn.Sequential(
            nn.Linear(384 + 5, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Linear(256, 128)
        )

    def forward(self, user_features, video_features):
        user_emb = self.user_tower(user_features)
        user_emb = F.normalize(user_emb, p=2, dim=-1)
        
        video_emb = self.video_tower(video_features)
        video_emb = F.normalize(video_emb, p=2, dim=-1)
        
        return user_emb, video_emb

    def encode_user(self, tag_weights_dict: dict[str, float], event_count: float, account_age_days: float) -> np.ndarray:
        self.eval()
        with torch.no_grad():
            vectors = []
            weights = []
            for tag_id, weight in tag_weights_dict.items():
                if str(tag_id) in self.tag_embeddings:
                    vectors.append(self.tag_embeddings[str(tag_id)])
                    weights.append(float(weight))
            
            if vectors:
                tag_vector = np.average(vectors, axis=0, weights=weights)
            else:
                tag_vector = np.zeros(384, dtype=np.float32)
                    
            user_meta = np.array([
                min(event_count / 10000.0, 1.0),
                min(account_age_days / 365.0, 1.0),
            ], dtype=np.float32)
            
            x = np.concatenate([tag_vector, user_meta])
            features = torch.tensor(x, dtype=torch.float32).unsqueeze(0)
            
            emb = self.user_tower(features)
            emb = F.normalize(emb, p=2, dim=-1)
            return emb.squeeze(0).numpy()

    def encode_video(self, tag_ids_list: list[str], view_count: float, like_rate: float, avg_watch_ratio: float, age_hours: float, duration_sec: float) -> np.ndarray:
        self.eval()
        with torch.no_grad():
            tag_vectors = [self.tag_embeddings[str(tag_id)] for tag_id in tag_ids_list if str(tag_id) in self.tag_embeddings]
            if tag_vectors:
                tag_vector = np.mean(tag_vectors, axis=0)
            else:
                tag_vector = np.zeros(384, dtype=np.float32)
                    
            video_meta = np.array([
                min(np.log1p(view_count) / 15.0, 1.0),
                min(like_rate, 1.0),
                min(avg_watch_ratio, 1.0),
                min(age_hours / (24 * 30), 1.0),
                min(duration_sec / 600.0, 1.0),
            ], dtype=np.float32)
            
            x = np.concatenate([tag_vector, video_meta])
            features = torch.tensor(x).unsqueeze(0)
            
            emb = self.video_tower(features)
            emb = F.normalize(emb, p=2, dim=-1)
            return emb.squeeze(0).numpy()

    def score(self, user_embedding: np.ndarray, video_embedding: np.ndarray) -> float:
        return float(np.dot(user_embedding, video_embedding))

    def save(self, path: str = "/app/storage/models/two_tower.pt"):
        torch.save({
            'model_state': self.state_dict(),
            'tag_vocab': self.tag_vocab,
            'num_tags': self.num_tags,
            'tag_embeddings': self.tag_embeddings
        }, path)

    @classmethod
    def load(cls, path: str = "/app/storage/models/two_tower.pt") -> 'TwoTowerModel':
        checkpoint = torch.load(path, map_location="cpu")
        model = cls.__new__(cls)
        super(TwoTowerModel, model).__init__()
        model.tag_vocab = checkpoint["tag_vocab"]
        model.num_tags = checkpoint["num_tags"]
        model.tag_embeddings = checkpoint.get("tag_embeddings", {})
        model._build_networks()
        model.load_state_dict(checkpoint["model_state"])
        model.eval()
        return model
