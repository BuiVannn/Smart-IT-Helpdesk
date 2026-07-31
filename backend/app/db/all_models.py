"""Import TOÀN BỘ model về một chỗ.

Alembic autogenerate chỉ nhìn thấy model đã được import. File này bảo đảm
mọi bảng đều xuất hiện trong metadata. THÊM MODULE MỚI thì thêm import vào đây.
"""

from app.db.base import Base  # noqa: F401
from app.modules.auth.models import RefreshToken  # noqa: F401
from app.modules.chatbot.models import (  # noqa: F401
    ChatCitation,
    ChatFeedback,
    ChatMessage,
    ChatSession,
)
from app.modules.feedback.models import TicketRating  # noqa: F401
from app.modules.knowledge.models import ArticleChunk, KbArticle, KbCategory  # noqa: F401
from app.modules.notifications.models import IdempotencyKey, Notification  # noqa: F401
from app.modules.tickets.models import (  # noqa: F401
    AiClassification,
    SlaPolicy,
    Ticket,
    TicketAttachment,
    TicketCategory,
    TicketComment,
    TicketEvent,
)
from app.modules.users.models import AgentSkill, Department, Holiday, User  # noqa: F401
