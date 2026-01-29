"""DynamoDB Operational Metadata Store - Fast Lookups, No Joins, No Drama.

This module provides a DynamoDB-backed store for operational metadata:
- Decision index: Fast lookups by decision_id, session_id, user_id
- Escalation tracking: Track escalations and their resolutions
- Human override references: Link overrides to original decisions
- No joins required - all data denormalized for performance

Design principles:
- DynamoDB for single-digit millisecond lookups
- Denormalized schema (no joins)
- Global secondary indexes for flexible queries
- TTL for automatic cleanup of old records
- Thread-safe operations

Environment variables:
- AWS_REGION: AWS region (default: us-east-1)
- AWS_PROFILE: AWS profile name (optional)
- DYNAMODB_METADATA_TABLE: DynamoDB table name
- DYNAMODB_PARTITION_KEY_PREFIX: Prefix for partition keys (default: metadata)
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class DynamoDBOperationalMetadata:
    """DynamoDB operational metadata store for fast lookups.
    
    Features:
    - Decision index: decision_id, session_id, user_id queries
    - Escalation tracking: escalation_id, decision_id, status
    - Human override references: override_id, original_decision_id, reviewer_id
    - Global secondary indexes for flexible queries
    - TTL for automatic cleanup
    - Denormalized schema for performance
    
    Table schema:
    - Partition Key: pk (PK#{metadata_type}#{primary_id})
    - Sort Key: sk (SK#{secondary_id}#{timestamp})
    - GSI1: gsi1_pk (entity_type), gsi1_sk (timestamp)
    - GSI2: gsi2_pk (user_id), gsi2_sk (timestamp)
    - TTL: ttl_timestamp (unix timestamp for auto-cleanup)
    """
    
    DEFAULT_REGION = "us-east-1"
    DEFAULT_TABLE_PREFIX = "metadata"
    DEFAULT_TTL_DAYS = 90  # Auto-cleanup old records
    
    def __init__(
        self,
        table_name: Optional[str] = None,
        region: Optional[str] = None,
        aws_profile: Optional[str] = None,
        partition_key_prefix: str = DEFAULT_TABLE_PREFIX,
        enable_ttl: bool = True,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ):
        """Initialize DynamoDB operational metadata store.
        
        Args:
            table_name: DynamoDB table name (or from DYNAMODB_METADATA_TABLE env var)
            region: AWS region (or from AWS_REGION env var)
            aws_profile: AWS profile name (optional)
            partition_key_prefix: Prefix for partition keys
            enable_ttl: Enable TTL for auto-cleanup
            ttl_days: Number of days to retain records
        """
        self.table_name = table_name or os.environ.get("DYNAMODB_METADATA_TABLE")
        if not self.table_name:
            raise ValueError(
                "DynamoDB table name required. Set DYNAMODB_METADATA_TABLE or pass table_name parameter."
            )
        
        self.region = region or os.environ.get("AWS_REGION", self.DEFAULT_REGION)
        self.partition_key_prefix = partition_key_prefix
        self.enable_ttl = enable_ttl
        self.ttl_days = ttl_days
        
        # Initialize DynamoDB resource
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile)
            self.dynamodb = session.resource("dynamodb", region_name=self.region)
        else:
            self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
        
        self.table = self.dynamodb.Table(self.table_name)
        
        logger.info(
            f"Initialized DynamoDBOperationalMetadata: table={self.table_name}, "
            f"region={self.region}, ttl_enabled={self.enable_ttl}"
        )
    
    def _get_ttl_timestamp(self) -> int:
        """Get TTL timestamp for record auto-cleanup.
        
        Returns:
            Unix timestamp (seconds from epoch)
        """
        if not self.enable_ttl:
            return 0
        
        future = datetime.now(timezone.utc) + timedelta(days=self.ttl_days)
        return int(future.timestamp())
    
    # ============================================================================
    # Decision Index - Fast lookups for decisions
    # ============================================================================
    
    def put_decision(
        self,
        decision_id: str,
        session_id: str,
        user_id: str,
        action: str,
        confidence_score: float,
        decided_by: str,
        policy_version: str,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Store decision metadata for fast lookups.
        
        Args:
            decision_id: Unique decision identifier
            session_id: Associated session ID
            user_id: Associated user ID
            action: Action taken (ALLOW/BLOCK/CHALLENGE/ESCALATE)
            confidence_score: Confidence score (0.0 to 1.0)
            decided_by: Who made the decision (AI/HUMAN/POLICY)
            policy_version: Version of policy rules used
            timestamp: Timestamp of decision
            metadata: Additional metadata
            
        Returns:
            decision_id
        """
        timestamp = timestamp or datetime.now(timezone.utc)
        
        item = {
            "pk": f"PK#DECISION#{decision_id}",
            "sk": f"SK#DECISION#{timestamp.isoformat()}",
            "entity_type": "DECISION",
            "decision_id": decision_id,
            "session_id": session_id,
            "user_id": user_id,
            "action": action,
            "confidence_score": Decimal(str(confidence_score)),
            "decided_by": decided_by,
            "policy_version": policy_version,
            "timestamp": timestamp.isoformat(),
            "gsi1_pk": f"DECISION#{user_id}",  # For user queries
            "gsi1_sk": timestamp.isoformat(),
            "gsi2_pk": f"SESSION#{session_id}",  # For session queries
            "gsi2_sk": timestamp.isoformat(),
        }
        
        if metadata:
            item["metadata"] = metadata
        
        if self.enable_ttl:
            item["ttl_timestamp"] = self._get_ttl_timestamp()
        
        try:
            self.table.put_item(Item=item)
            logger.debug(f"Stored decision metadata: {decision_id}")
            return decision_id
        except ClientError as e:
            logger.error(f"Failed to store decision metadata: {e}")
            raise
    
    def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Get decision metadata by decision_id.
        
        Args:
            decision_id: Decision ID to look up
            
        Returns:
            Decision metadata or None
        """
        try:
            response = self.table.get_item(
                Key={"pk": f"PK#DECISION#{decision_id}", "sk": f"SK#DECISION#"}
            )
            item = response.get("Item")
            if item:
                # Convert Decimal back to float
                if "confidence_score" in item:
                    item["confidence_score"] = float(item["confidence_score"])
                return dict(item)
            return None
        except ClientError as e:
            logger.error(f"Failed to get decision metadata: {e}")
            return None
    
    def query_decisions_by_user(
        self,
        user_id: str,
        limit: int = 100,
        start_timestamp: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Query decisions by user_id (fast via GSI).
        
        Args:
            user_id: User ID to query
            limit: Maximum number of results
            start_timestamp: Optional start timestamp filter
            
        Returns:
            List of decision metadata
        """
        try:
            key_condition = "gsi1_pk = :user_id"
            expr_values = {":user_id": f"DECISION#{user_id}"}
            
            if start_timestamp:
                key_condition += " AND gsi1_sk >= :timestamp"
                expr_values[":timestamp"] = start_timestamp.isoformat()
            
            response = self.table.query(
                IndexName="gsi1_pk-gsi1_sk-index",
                KeyConditionExpression=key_condition,
                ExpressionAttributeValues=expr_values,
                Limit=limit,
                ScanIndexForward=False,  # Most recent first
            )
            
            items = response.get("Items", [])
            for item in items:
                if "confidence_score" in item:
                    item["confidence_score"] = float(item["confidence_score"])
            
            return [dict(item) for item in items]
        except ClientError as e:
            logger.error(f"Failed to query decisions by user: {e}")
            return []
    
    def query_decisions_by_session(
        self,
        session_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query decisions by session_id (fast via GSI).
        
        Args:
            session_id: Session ID to query
            limit: Maximum number of results
            
        Returns:
            List of decision metadata
        """
        try:
            response = self.table.query(
                IndexName="gsi2_pk-gsi2_sk-index",
                KeyConditionExpression="gsi2_pk = :session_id",
                ExpressionAttributeValues={":session_id": f"SESSION#{session_id}"},
                Limit=limit,
                ScanIndexForward=False,  # Most recent first
            )
            
            items = response.get("Items", [])
            for item in items:
                if "confidence_score" in item:
                    item["confidence_score"] = float(item["confidence_score"])
            
            return [dict(item) for item in items]
        except ClientError as e:
            logger.error(f"Failed to query decisions by session: {e}")
            return []
    
    # ============================================================================
    # Escalation Tracking - Track escalations and resolutions
    # ============================================================================
    
    def create_escalation(
        self,
        decision_id: str,
        escalation_type: str,
        reason: str,
        escalated_to: str,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create an escalation record.
        
        Args:
            decision_id: Decision that triggered escalation
            escalation_type: Type of escalation (POLICY/THRESHOLD/MANUAL)
            reason: Reason for escalation
            escalated_to: Who escalation goes to (team/analyst/human)
            timestamp: Timestamp of escalation
            metadata: Additional metadata
            
        Returns:
            escalation_id
        """
        escalation_id = f"esc_{uuid4().hex[:12]}"
        timestamp = timestamp or datetime.now(timezone.utc)
        
        item = {
            "pk": f"PK#ESCALATION#{escalation_id}",
            "sk": f"SK#ESCALATION#{timestamp.isoformat()}",
            "entity_type": "ESCALATION",
            "escalation_id": escalation_id,
            "decision_id": decision_id,
            "escalation_type": escalation_type,
            "reason": reason,
            "escalated_to": escalated_to,
            "status": "PENDING",
            "timestamp": timestamp.isoformat(),
            "gsi1_pk": f"ESCALATION#{escalation_type}",
            "gsi1_sk": timestamp.isoformat(),
            "gsi2_pk": f"DECISION#{decision_id}",
            "gsi2_sk": timestamp.isoformat(),
        }
        
        if metadata:
            item["metadata"] = metadata
        
        if self.enable_ttl:
            item["ttl_timestamp"] = self._get_ttl_timestamp()
        
        try:
            self.table.put_item(Item=item)
            logger.debug(f"Created escalation: {escalation_id}")
            return escalation_id
        except ClientError as e:
            logger.error(f"Failed to create escalation: {e}")
            raise
    
    def update_escalation_status(
        self,
        escalation_id: str,
        status: str,
        resolution: Optional[str] = None,
        resolved_by: Optional[str] = None,
    ) -> bool:
        """Update escalation status (e.g., PENDING -> RESOLVED).
        
        Args:
            escalation_id: Escalation ID to update
            status: New status (PENDING/RESOLVED/REJECTED)
            resolution: Resolution details
            resolved_by: Who resolved it
            
        Returns:
            True if successful
        """
        try:
            update_expr = "SET #status = :status"
            expr_values = {":status": status}
            expr_names = {"#status": "status"}
            
            if resolution:
                update_expr += ", resolution = :resolution"
                expr_values[":resolution"] = resolution
            
            if resolved_by:
                update_expr += ", resolved_by = :resolved_by"
                expr_values[":resolved_by"] = resolved_by
            
            update_expr += ", updated_at = :updated_at"
            expr_values[":updated_at"] = datetime.now(timezone.utc).isoformat()
            
            self.table.update_item(
                Key={
                    "pk": f"PK#ESCALATION#{escalation_id}",
                    "sk": f"SK#ESCALATION#",  # Truncated SK for update
                },
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )
            logger.debug(f"Updated escalation status: {escalation_id} -> {status}")
            return True
        except ClientError as e:
            logger.error(f"Failed to update escalation: {e}")
            return False
    
    def get_escalations_by_decision(
        self,
        decision_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all escalations for a decision.
        
        Args:
            decision_id: Decision ID to query
            
        Returns:
            List of escalation records
        """
        try:
            response = self.table.query(
                IndexName="gsi2_pk-gsi2_sk-index",
                KeyConditionExpression="gsi2_pk = :decision_id",
                ExpressionAttributeValues={":decision_id": f"DECISION#{decision_id}"},
                ScanIndexForward=False,
            )
            
            return [dict(item) for item in response.get("Items", [])]
        except ClientError as e:
            logger.error(f"Failed to get escalations by decision: {e}")
            return []
    
    # ============================================================================
    # Human Override References - Link overrides to decisions
    # ============================================================================
    
    def create_override_reference(
        self,
        override_id: str,
        original_decision_id: str,
        reviewer_id: str,
        override_type: str,
        reason: str,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a human override reference record.
        
        Args:
            override_id: Unique override identifier
            original_decision_id: Original decision that was overridden
            reviewer_id: Reviewer who made the override
            override_type: Type of override (APPROVE/REJECT/MODIFY)
            reason: Reason for override
            timestamp: Timestamp of override
            metadata: Additional metadata (new_action, etc.)
            
        Returns:
            override_id
        """
        timestamp = timestamp or datetime.now(timezone.utc)
        
        item = {
            "pk": f"PK#OVERRIDE#{override_id}",
            "sk": f"SK#OVERRIDE#{timestamp.isoformat()}",
            "entity_type": "OVERRIDE",
            "override_id": override_id,
            "original_decision_id": original_decision_id,
            "reviewer_id": reviewer_id,
            "override_type": override_type,
            "reason": reason,
            "timestamp": timestamp.isoformat(),
            "gsi1_pk": f"OVERRIDE#{reviewer_id}",  # For reviewer queries
            "gsi1_sk": timestamp.isoformat(),
            "gsi2_pk": f"DECISION#{original_decision_id}",  # For decision queries
            "gsi2_sk": timestamp.isoformat(),
        }
        
        if metadata:
            item["metadata"] = metadata
        
        if self.enable_ttl:
            item["ttl_timestamp"] = self._get_ttl_timestamp()
        
        try:
            self.table.put_item(Item=item)
            logger.debug(f"Created override reference: {override_id}")
            return override_id
        except ClientError as e:
            logger.error(f"Failed to create override reference: {e}")
            raise
    
    def get_override_for_decision(
        self,
        decision_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get the override record (if any) for a decision.
        
        Args:
            decision_id: Decision ID to query
            
        Returns:
            Override record or None
        """
        try:
            response = self.table.query(
                IndexName="gsi2_pk-gsi2_sk-index",
                KeyConditionExpression="gsi2_pk = :decision_id AND entity_type = :entity_type",
                ExpressionAttributeValues={
                    ":decision_id": f"DECISION#{decision_id}",
                    ":entity_type": "OVERRIDE",
                },
                Limit=1,
            )
            
            items = response.get("Items", [])
            return dict(items[0]) if items else None
        except ClientError as e:
            logger.error(f"Failed to get override for decision: {e}")
            return None
    
    def get_overrides_by_reviewer(
        self,
        reviewer_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get all overrides by a reviewer (fast via GSI).
        
        Args:
            reviewer_id: Reviewer ID to query
            limit: Maximum number of results
            
        Returns:
            List of override records
        """
        try:
            response = self.table.query(
                IndexName="gsi1_pk-gsi1_sk-index",
                KeyConditionExpression="gsi1_pk = :reviewer_id",
                ExpressionAttributeValues={":reviewer_id": f"OVERRIDE#{reviewer_id}"},
                Limit=limit,
                ScanIndexForward=False,
            )
            
            return [dict(item) for item in response.get("Items", [])]
        except ClientError as e:
            logger.error(f"Failed to get overrides by reviewer: {e}")
            return []
    
    # ============================================================================
    # Utility methods
    # ============================================================================
    
    def health_check(self) -> bool:
        """Check DynamoDB table health.
        
        Returns:
            True if table is accessible
        """
        try:
            self.table.table_status
            return True
        except Exception as e:
            logger.error(f"DynamoDB health check failed: {e}")
            return False
