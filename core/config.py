from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-v4-pro"

    chunk_size: int = 800
    chunk_overlap: int = 100

    retriever_top_k: int = 5

    # —— 自适应检索 ——
    retriever_adaptive: bool = True
    retriever_fetch_k: int = 20          # 初次召回的大池规模
    retriever_score_threshold: float = 0.75  # cosine distance，越小越相关；≤阈值才保留
    # 注：针对默认双语模型校准——问句↔段落的真实命中约 0.5~0.65，噪声约 >0.9
    retriever_min_k: int = 3             # 兜底最少返回，保证有上下文
    retriever_max_k: int = 10            # 上限，避免上下文过长

    llm_temperature: float = 0.2
    llm_max_tokens: int = 20480

    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    upload_dir: str = "data/uploads"
    vectorstore_dir: str = "data/vectorstore"
    log_dir: str = "logs"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_port: int = 8501

    @property
    def upload_path(self) -> Path:
        p = PROJECT_ROOT / self.upload_dir
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def vectorstore_path(self) -> Path:
        p = PROJECT_ROOT / self.vectorstore_dir
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def log_path(self) -> Path:
        p = PROJECT_ROOT / self.log_dir
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
