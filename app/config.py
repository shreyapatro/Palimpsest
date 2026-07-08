from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    dashscope_api_key: str
    dashscope_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    model_classify: str = "qwen3.6-flash"
    model_response: str = "qwen3.7-plus"
    model_compression: str = "qwen3.7-plus"
    model_conflict: str = "qwen3.7-max"
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 1024

    database_url: str

    context_budget_top_k: int = 8
    conflict_similarity_threshold: float = 0.80
    compression_score_threshold: float = 0.25
    compression_min_cluster_size: int = 3
    cluster_similarity_threshold: float = 0.72
    maintenance_interval_seconds: int = 300

    class Config:
        env_file = ".env"


settings = Settings()
