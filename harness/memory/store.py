"""内存版记忆存储 — 模拟 Mem0 三层记忆体系"""

import time
import re
from typing import Any, Dict, List, Optional
from collections import OrderedDict


class MemoryStore:
    """三层记忆存储（内存版）

    - session_store: 会话记忆，会话结束可清理
    - user_store: 用户长期记忆（偏好、历史行为）
    - entity_store: 实体记忆（客户、基金、报告等业务对象）
    """

    def __init__(self):
        # { user_id/session_id: [ {content, metadata, timestamp}, ... ] }
        self.session_store: Dict[str, List[Dict]] = {}
        self.user_store: Dict[str, List[Dict]] = {}
        self.entity_store: Dict[str, List[Dict]] = {}  # key: entity_type
        self._id_counter = 0

    # ── 写入 ────────────────────────────────────────

    def add(self, content: str, user_id: str = "default",
            session_id: str = "", memory_type: str = "session",
            metadata: Dict = None) -> str:
        """添加一条记忆

        Args:
            content: 记忆内容
            user_id: 用户 ID
            session_id: 会话 ID（type=session 时必填）
            memory_type: session | user | entity
            metadata: 附加元数据
        """
        self._id_counter += 1
        entry = {
            "id": f"mem_{self._id_counter}",
            "content": content,
            "user_id": user_id,
            "session_id": session_id,
            "metadata": metadata or {},
            "timestamp": time.time(),
        }

        if memory_type == "session":
            key = session_id or user_id
            self.session_store.setdefault(key, []).append(entry)
        elif memory_type == "user":
            self.user_store.setdefault(user_id, []).append(entry)
        elif memory_type == "entity":
            entity_type = (metadata or {}).get("entity_type", "general")
            self.entity_store.setdefault(entity_type, []).append(entry)

        return entry["id"]

    # ── 检索 ────────────────────────────────────────

    def search(self, query: str, user_id: str = "default",
               session_id: str = "", top_k: int = 5) -> Dict[str, List[Dict]]:
        """混合检索三层记忆

        Args:
            query: 查询文本
            user_id: 用户 ID
            session_id: 会话 ID
            top_k: 每层返回的最大条目数

        Returns:
            {
                "session_context": [...],
                "user_context": [...],
                "entity_context": [...]
            }
        """
        keywords = self._tokenize(query)

        return {
            "session_context": self._search_store(
                self.session_store.get(session_id or user_id, []), keywords, top_k
            ),
            "user_context": self._search_store(
                self.user_store.get(user_id, []), keywords, top_k
            ),
            "entity_context": self._search_store_cross_entity(keywords, top_k),
        }

    def _search_store(self, entries: List[Dict], keywords: List[str], top_k: int) -> List[Dict]:
        """单层关键词搜索 + 时间衰减"""
        scored = []
        for entry in entries:
            score = self._match_score(entry["content"], keywords)
            # 时间衰减：1 小时内的记忆权重 ×1.5
            age_hours = (time.time() - entry["timestamp"]) / 3600
            if age_hours < 1:
                score *= 1.5
            elif age_hours > 168:  # 一周以上衰减
                score *= 0.5
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def _search_store_cross_entity(self, keywords: List[str], top_k: int) -> List[Dict]:
        """跨实体检索"""
        all_results = []
        for entries in self.entity_store.values():
            scored = []
            for entry in entries:
                score = self._match_score(entry["content"], keywords)
                if score > 0:
                    scored.append((score, entry))
            all_results.extend(scored)
        all_results.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in all_results[:top_k]]

    # ── 删除 ────────────────────────────────────────

    def delete(self, memory_id: str) -> bool:
        """删除一条记忆"""
        for store in [self.session_store, self.user_store, self.entity_store]:
            for key, entries in store.items():
                for i, entry in enumerate(entries):
                    if entry["id"] == memory_id:
                        del entries[i]
                        return True
        return False

    def clear_session(self, session_id: str) -> int:
        """清除指定会话的记忆"""
        count = len(self.session_store.get(session_id, []))
        self.session_store.pop(session_id, None)
        return count

    # ── 统计 ────────────────────────────────────────

    def get_stats(self) -> Dict:
        """获取记忆统计"""
        return {
            "session_memories": sum(len(v) for v in self.session_store.values()),
            "session_count": len(self.session_store),
            "user_memories": sum(len(v) for v in self.user_store.values()),
            "user_count": len(self.user_store),
            "entity_memories": sum(len(v) for v in self.entity_store.values()),
            "entity_types": list(self.entity_store.keys()),
        }

    def get_all_memories(self, user_id: str = None) -> List[Dict]:
        """获取所有记忆（管理后台查询用）"""
        all_memories = []
        for entries in self.session_store.values():
            all_memories.extend(entries)
        if user_id:
            all_memories.extend(self.user_store.get(user_id, []))
        else:
            for entries in self.user_store.values():
                all_memories.extend(entries)
        for entries in self.entity_store.values():
            all_memories.extend(entries)
        all_memories.sort(key=lambda x: x["timestamp"], reverse=True)
        return all_memories

    # ── 辅助 ────────────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """中文简单分词（按标点、空格切分）"""
        # 简单实现：按常见分隔符 + 2-gram
        text = text.lower()
        tokens = re.split(r'[，。！？；、\s,\.!\?;]+', text)
        tokens = [t.strip() for t in tokens if len(t.strip()) >= 2]
        # 补充 2-gram（中文）
        bigrams = []
        for token in "".join(tokens):
            bigrams.append(token)
        return list(set(tokens + bigrams))

    @staticmethod
    def _match_score(content: str, keywords: List[str]) -> float:
        """关键词匹配评分"""
        if not keywords:
            return 0.0
        content_lower = content.lower()
        score = 0.0
        for kw in keywords:
            if kw in content_lower:
                score += 1.0
            # 部分匹配
            for char in kw:
                if char in content_lower:
                    score += 0.1
        return score


# 全局 Memory Store 单例
memory_store = MemoryStore()
