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

    llm_temperature: float = 0.2
    llm_max_tokens: int = 2048

    embedding_model: str = "all-MiniLM-L6-v2"

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
