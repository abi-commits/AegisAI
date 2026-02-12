"""DynamoDB Operational Metadata Store for decisions, escalations, and overrides."""

import logging, os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

import boto3
from aegis_ai.common.constants import DataConstants
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class DynamoDBOperationalMetadata:
    """DynamoDB store for decisions, escalations, and overrides."""
    
    DEFAULT_REGION = "us-east-1"
    DEFAULT_TABLE_PREFIX = "metadata"
    DEFAULT_TTL_DAYS = 90
    
    def __init__(
        self,
        table_name: Optional[str] = None,
        region: Optional[str] = None,
        aws_profile: Optional[str] = None,
        partition_key_prefix: str = DEFAULT_TABLE_PREFIX,
        enable_ttl: bool = True,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ):
        self.table_name = table_name or os.environ.get("DYNAMODB_METADATA_TABLE")
        if not self.table_name:
            raise ValueError("DYNAMODB_METADATA_TABLE required")
        
        self.region = region or os.environ.get("AWS_REGION", self.DEFAULT_REGION)
        self.partition_key_prefix = partition_key_prefix
        self.enable_ttl = enable_ttl
        self.ttl_days = ttl_days
        
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile)
            self.dynamodb = session.resource("dynamodb", region_name=self.region)
        else:
            self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
        
        self.table = self.dynamodb.Table(self.table_name)
        logger.info(f"DynamoDB initialized: {self.table_name} ({self.region})")
    
    def _get_ttl_timestamp(self) -> int:
        if not self.enable_ttl:
            return 0
        future = datetime.now(timezone.utc) + timedelta(days=self.ttl_days)
        return int(future.timestamp())
    
    def _build_item(
        self, entity_type: str, primary_id: str, timestamp: datetime,
        data: Dict[str, Any], gsi_keys: Optional[Dict[str, tuple]] = None
    ) -> Dict[str, Any]:
        """Build DynamoDB item with standard structure.
        
        Args:
            entity_type: DECISION|ESCALATION|OVERRIDE
            primary_id: Primary identifier
            timestamp: Record timestamp
            data: Core data fields
            gsi_keys: GSI key pairs {gsi1: (pk, sk), gsi2: (pk, sk)}
        """
        item = {
            "pk": f"PK#{entity_type}#{primary_id}",
            "sk": f"SK#{entity_type}#{timestamp.isoformat()}",
            "entity_type": entity_type,
            **data,
        }
        
        if gsi_keys:
            if "gsi1" in gsi_keys:
                item["gsi1_pk"], item["gsi1_sk"] = gsi_keys["gsi1"]
            if "gsi2" in gsi_keys:
                item["gsi2_pk"], item["gsi2_sk"] = gsi_keys["gsi2"]
        
        if self.enable_ttl:
            item["ttl_timestamp"] = self._get_ttl_timestamp()
        
        return item
    
    def _query_index(self, index: str, pk_value: str, limit: int = DataConstants.DEFAULT_QUERY_LIMIT, 
        timestamp_filter: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Query GSI with consistent error handling."""
        try:
            expr_values = {":pk": pk_value}
            key_cond = f"{index.split('-')[0]} = :pk"
            
            if timestamp_filter:
                key_cond += " AND gsi1_sk >= :ts"
                expr_values[":ts"] = timestamp_filter.isoformat()
            
            response = self.table.query(
                IndexName=f"{index}-index",
                KeyConditionExpression=key_cond,
                ExpressionAttributeValues=expr_values,
                Limit=limit,
                ScanIndexForward=False,
            )
            
            items = response.get("Items", [])
            for item in items:
                if "confidence_score" in item:
                    item["confidence_score"] = float(item["confidence_score"])
            return [dict(i) for i in items]
        except ClientError as e:
            logger.error(f"Query failed ({index}): {e}")
            return []
    
    # ========== DECISION INDEX ==========
    
    def put_decision(
        self, decision_id: str, session_id: str, user_id: str, action: str,
        confidence_score: float, decided_by: str, policy_version: str,
        timestamp: Optional[datetime] = None, metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        timestamp = timestamp or datetime.now(timezone.utc)
        item = self._build_item(
            "DECISION", decision_id, timestamp,
            {
                "decision_id": decision_id, "session_id": session_id,
                "user_id": user_id, "action": action,
                "confidence_score": Decimal(str(confidence_score)),
                "decided_by": decided_by, "policy_version": policy_version,
                "timestamp": timestamp.isoformat(), **(metadata or {}),
            },
            {"gsi1": (f"DECISION#{user_id}", timestamp.isoformat()),
             "gsi2": (f"SESSION#{session_id}", timestamp.isoformat())}
        )
        try:
            self.table.put_item(Item=item)
            return decision_id
        except ClientError as e:
            logger.error(f"put_decision failed: {e}")
            raise
    
    def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        try:
            resp = self.table.get_item(Key={"pk": f"PK#DECISION#{decision_id}", "sk": "SK#DECISION#"})
            if item := resp.get("Item"):
                if "confidence_score" in item:
                    item["confidence_score"] = float(item["confidence_score"])
                return dict(item)
            return None
        except ClientError as e:
            logger.error(f"get_decision failed: {e}")
            return None
    
    def query_decisions_by_user(self, user_id: str, limit: int = DataConstants.DEFAULT_QUERY_LIMIT, start_timestamp: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        return self._query_index("gsi1_pk-gsi1_sk", f"DECISION#{user_id}", limit, start_timestamp)
    
    def query_decisions_by_session(self, session_id: str, limit: int = DataConstants.DEFAULT_QUERY_LIMIT) -> List[Dict[str, Any]]:
        return self._query_index("gsi2_pk-gsi2_sk", f"SESSION#{session_id}", limit)
    
    # ========== ESCALATION TRACKING ==========
    
    def create_escalation(
        self, decision_id: str, escalation_type: str, reason: str, escalated_to: str,
        timestamp: Optional[datetime] = None, metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        escalation_id = f"esc_{uuid4().hex[:12]}"
        timestamp = timestamp or datetime.now(timezone.utc)
        item = self._build_item(
            "ESCALATION", escalation_id, timestamp,
            {
                "escalation_id": escalation_id, "decision_id": decision_id,
                "escalation_type": escalation_type, "reason": reason,
                "escalated_to": escalated_to, "status": "PENDING",
                "timestamp": timestamp.isoformat(), **(metadata or {}),
            },
            {"gsi1": (f"ESCALATION#{escalation_type}", timestamp.isoformat()),
             "gsi2": (f"DECISION#{decision_id}", timestamp.isoformat())}
        )
        try:
            self.table.put_item(Item=item)
            return escalation_id
        except ClientError as e:
            logger.error(f"create_escalation failed: {e}")
            raise
    
    def update_escalation_status(
        self, escalation_id: str, status: str,
        resolution: Optional[str] = None, resolved_by: Optional[str] = None,
    ) -> bool:
        try:
            expr_values = {":status": status, ":updated": datetime.now(timezone.utc).isoformat()}
            expr = "SET #status = :status, updated_at = :updated"
            expr_names = {"#status": "status"}
            
            if resolution:
                expr_values[":resolution"] = resolution
                expr += ", resolution = :resolution"
            if resolved_by:
                expr_values[":resolved_by"] = resolved_by
                expr += ", resolved_by = :resolved_by"
            
            self.table.update_item(
                Key={"pk": f"PK#ESCALATION#{escalation_id}", "sk": "SK#ESCALATION#"},
                UpdateExpression=expr, ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )
            return True
        except ClientError as e:
            logger.error(f"update_escalation_status failed: {e}")
            return False
    
    def get_escalations_by_decision(self, decision_id: str) -> List[Dict[str, Any]]:
        return self._query_index("gsi2_pk-gsi2_sk", f"DECISION#{decision_id}")
    
    # ========== HUMAN OVERRIDES ==========
    
    def create_override_reference(
        self, override_id: str, original_decision_id: str, reviewer_id: str,
        override_type: str, reason: str, timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        timestamp = timestamp or datetime.now(timezone.utc)
        item = self._build_item(
            "OVERRIDE", override_id, timestamp,
            {
                "override_id": override_id, "original_decision_id": original_decision_id,
                "reviewer_id": reviewer_id, "override_type": override_type,
                "reason": reason, "timestamp": timestamp.isoformat(), **(metadata or {}),
            },
            {"gsi1": (f"OVERRIDE#{reviewer_id}", timestamp.isoformat()),
             "gsi2": (f"DECISION#{original_decision_id}", timestamp.isoformat())}
        )
        try:
            self.table.put_item(Item=item)
            return override_id
        except ClientError as e:
            logger.error(f"create_override_reference failed: {e}")
            raise
    
    def get_override_for_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        try:
            resp = self.table.query(
                IndexName="gsi2_pk-gsi2_sk-index",
                KeyConditionExpression="gsi2_pk = :did",
                ExpressionAttributeValues={":did": f"DECISION#{decision_id}"},
                Limit=1,
            )
            return dict(resp["Items"][0]) if resp.get("Items") else None
        except ClientError as e:
            logger.error(f"get_override_for_decision failed: {e}")
            return None
    
    def get_overrides_by_reviewer(self, reviewer_id: str, limit: int = DataConstants.DEFAULT_QUERY_LIMIT) -> List[Dict[str, Any]]:
        return self._query_index("gsi1_pk-gsi1_sk", f"OVERRIDE#{reviewer_id}", limit)
    
    def health_check(self) -> bool:
        try:
            self.table.table_status
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
