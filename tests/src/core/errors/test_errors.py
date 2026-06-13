"""Tests for src/core/errors module - all 24+ error classes."""
import pytest

from src.core.errors import (
    ProviderError,
    PlatformError,
    NoCandidateError,
    AuthError,
    LoginError,
    TokenExpiredError,
    UploadError,
    PoWError,
    EmbeddingError,
    RateLimitError,
    ModelNotFoundError,
    ContextLengthError,
    NetworkError,
    StreamError,
    ConfigError,
    ValidationError,
    QuotaExceededError,
    ServerError,
    RequestTimeoutError,
    NotSupportedError,
    ImageError,
    AudioError,
    VideoError,
    RerankError,
    ModerationError,
    FileError,
    BatchError,
    classify_http_error,
)


class TestProviderError:
    def test_basic_creation(self):
        err = ProviderError("test error")
        assert str(err) == "test error"
        assert err.original is None
        assert err.status_code == 500

    def test_with_original_exception(self):
        original = ValueError("original")
        err = ProviderError("wrapper", original=original)
        assert err.original is original

    def test_custom_status_code(self):
        err = ProviderError("bad request", status_code=400)
        assert err.status_code == 400

    def test_is_exception(self):
        err = ProviderError("test")
        assert isinstance(err, Exception)


class TestPlatformError:
    def test_inheritance(self):
        err = PlatformError("platform error")
        assert isinstance(err, ProviderError)

    def test_default_status_code(self):
        err = PlatformError("test")
        assert err.status_code == 500


class TestAuthError:
    def test_status_code_401(self):
        err = AuthError("invalid credentials")
        assert err.status_code == 401

    def test_inheritance(self):
        err = AuthError("test")
        assert isinstance(err, PlatformError)
        assert isinstance(err, ProviderError)


class TestLoginError:
    def test_inherits_from_auth(self):
        err = LoginError("wrong password")
        assert isinstance(err, AuthError)
        assert err.status_code == 401


class TestTokenExpiredError:
    def test_inherits_from_auth(self):
        err = TokenExpiredError("token expired")
        assert isinstance(err, AuthError)
        assert err.status_code == 401


class TestUploadError:
    def test_status_code_502(self):
        err = UploadError("upload failed")
        assert err.status_code == 502


class TestPoWError:
    def test_inheritance(self):
        err = PoWError("pow failed")
        assert isinstance(err, PlatformError)


class TestEmbeddingError:
    def test_inheritance(self):
        err = EmbeddingError("embedding failed")
        assert isinstance(err, PlatformError)


class TestRateLimitError:
    def test_status_code_429(self):
        err = RateLimitError("rate limited")
        assert err.status_code == 429

    def test_retry_after(self):
        err = RateLimitError("rate limited", retry_after=60.0)
        assert err.retry_after == 60.0

    def test_default_message(self):
        err = RateLimitError()
        assert "请求频率超限" in str(err)


class TestModelNotFoundError:
    def test_status_code_404(self):
        err = ModelNotFoundError(model="gpt-5")
        assert err.status_code == 404

    def test_message_contains_model(self):
        err = ModelNotFoundError(model="test-model")
        assert "test-model" in str(err)

    def test_model_attribute(self):
        err = ModelNotFoundError(model="test-model")
        assert err.model == "test-model"


class TestContextLengthError:
    def test_status_code_400(self):
        err = ContextLengthError("too long")
        assert err.status_code == 400

    def test_default_message(self):
        err = ContextLengthError()
        assert "上下文" in str(err) or "context" in str(err).lower()


class TestStreamError:
    def test_inheritance(self):
        err = StreamError("stream interrupted")
        assert isinstance(err, PlatformError)


class TestServerError:
    def test_status_code_502(self):
        err = ServerError("internal error")
        assert err.status_code == 502

    def test_http_status_attribute(self):
        err = ServerError("error", http_status=503)
        assert err.http_status == 503

    def test_default_http_status(self):
        err = ServerError("error")
        assert err.http_status == 500


class TestImageError:
    def test_inheritance(self):
        err = ImageError("image generation failed")
        assert isinstance(err, PlatformError)


class TestAudioError:
    def test_inheritance(self):
        err = AudioError("audio processing failed")
        assert isinstance(err, PlatformError)


class TestVideoError:
    def test_inheritance(self):
        err = VideoError("video generation failed")
        assert isinstance(err, PlatformError)


class TestRerankError:
    def test_inheritance(self):
        err = RerankError("rerank failed")
        assert isinstance(err, PlatformError)


class TestModerationError:
    def test_inheritance(self):
        err = ModerationError("content blocked")
        assert isinstance(err, PlatformError)


class TestFileError:
    def test_inheritance(self):
        err = FileError("file operation failed")
        assert isinstance(err, PlatformError)


class TestBatchError:
    def test_inheritance(self):
        err = BatchError("batch request failed")
        assert isinstance(err, PlatformError)


class TestQuotaExceededError:
    def test_status_code_402(self):
        err = QuotaExceededError("quota exceeded")
        assert err.status_code == 402

    def test_default_message(self):
        err = QuotaExceededError()
        assert "耗尽" in str(err) or "quota" in str(err).lower()


class TestNoCandidateError:
    def test_status_code_503(self):
        err = NoCandidateError("no candidates")
        assert err.status_code == 503

    def test_default_message(self):
        err = NoCandidateError()
        assert "候选项" in str(err) or "candidate" in str(err).lower()


class TestNetworkError:
    def test_status_code_502(self):
        err = NetworkError("connection failed")
        assert err.status_code == 502


class TestConfigError:
    def test_status_code_500(self):
        err = ConfigError("invalid config")
        assert err.status_code == 500


class TestValidationError:
    def test_status_code_400(self):
        err = ValidationError("invalid field")
        assert err.status_code == 400

    def test_field_attribute(self):
        err = ValidationError("invalid", field="username")
        assert err.field == "username"


class TestRequestTimeoutError:
    def test_status_code_504(self):
        err = RequestTimeoutError("timeout")
        assert err.status_code == 504

    def test_default_message(self):
        err = RequestTimeoutError()
        assert "超时" in str(err) or "timeout" in str(err).lower()


class TestNotSupportedError:
    def test_status_code_501(self):
        err = NotSupportedError("vision")
        assert err.status_code == 501

    def test_feature_attribute(self):
        err = NotSupportedError("code_exec")
        assert err.feature == "code_exec"

    def test_message_contains_feature(self):
        err = NotSupportedError("vision")
        assert "vision" in str(err)


class TestClassifyHttpError:
    def test_400_context_length(self):
        err = classify_http_error(400, "prompt is too long, maximum context length exceeded")
        assert isinstance(err, ContextLengthError)

    def test_400_validation(self):
        err = classify_http_error(400, "invalid field format")
        assert isinstance(err, ValidationError)

    def test_401_auth(self):
        err = classify_http_error(401, "invalid credentials")
        assert isinstance(err, AuthError)

    def test_402_quota(self):
        err = classify_http_error(402, "quota exceeded")
        assert isinstance(err, QuotaExceededError)

    def test_404_model(self):
        err = classify_http_error(404, "gpt-5")
        assert isinstance(err, ModelNotFoundError)
        assert err.model == "gpt-5"

    def test_408_timeout(self):
        err = classify_http_error(408, "request timeout")
        assert isinstance(err, RequestTimeoutError)

    def test_429_rate_limit(self):
        err = classify_http_error(429, "rate limit exceeded")
        assert isinstance(err, RateLimitError)

    def test_500_server_error(self):
        err = classify_http_error(500, "internal server error")
        assert isinstance(err, ServerError)
        assert err.http_status == 500

    def test_503_server_error(self):
        err = classify_http_error(503, "service unavailable")
        assert isinstance(err, ServerError)

    def test_504_gateway_timeout(self):
        err = classify_http_error(504, "gateway timeout")
        assert isinstance(err, RequestTimeoutError)

    def test_unknown_status_returns_platform_error(self):
        err = classify_http_error(418, "I'm a teapot")
        assert isinstance(err, PlatformError)

    def test_with_original_exception(self):
        original = ValueError("original")
        err = classify_http_error(500, "error", original=original)
        assert err.original is original
