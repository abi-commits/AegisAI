"""Human-in-the-Loop Review System - Real Authority, Real UI.

Features:
- Case state management (DynamoDB)
- Evidence snapshot storage (S3)
- Review actions (Approve, Override, Comment)
- Mandatory commenting on overrides
- Override layering (never delete AI output)
- Reviewer authority tracking
"""

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from decimal import Decimal
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class CaseStatus(str, Enum):
    """States of a review case."""
    PENDING = "PENDING"            # Awaiting review
    IN_REVIEW = "IN_REVIEW"        # Being reviewed
    APPROVED = "APPROVED"          # Approved by reviewer
    REJECTED = "REJECTED"          # Rejected by reviewer
    OVERRIDDEN = "OVERRIDDEN"      # AI decision overridden
    DEFERRED = "DEFERRED"          # Deferred for later
    ESCALATED = "ESCALATED"        # Escalated to manager


class ReviewAction(str, Enum):
    """Actions a reviewer can take."""
    APPROVE = "APPROVE"            # Approve AI decision
    REJECT = "REJECT"              # Reject AI decision
    OVERRIDE = "OVERRIDE"          # Override with new action
    COMMENT = "COMMENT"            # Add comment
    DEFER = "DEFER"                # Defer decision
    ESCALATE = "ESCALATE"          # Escalate to manager


class CaseManager:
    """Manages review cases with state and evidence.
    
    Features:
    - Case state in DynamoDB
    - Evidence snapshots in S3
    - Review history
    - Mandatory comments on overrides
    - Reviewer tracking
    
    Environment variables:
    - DYNAMODB_CASES_TABLE: DynamoDB table for cases
    - S3_EVIDENCE_BUCKET: S3 bucket for evidence snapshots
    - AWS_REGION: AWS region
    """
    
    DEFAULT_REGION = "us-east-1"
    
    def __init__(
        self,
        cases_table: Optional[str] = None,
        evidence_bucket: Optional[str] = None,
        region: Optional[str] = None,
        aws_profile: Optional[str] = None,
    ):
        """Initialize case manager.
        
        Args:
            cases_table: DynamoDB table for cases (or env var)
            evidence_bucket: S3 bucket for evidence (or env var)
            region: AWS region
            aws_profile: AWS profile name
        """
        import os
        
        self.cases_table_name = cases_table or os.environ.get("DYNAMODB_CASES_TABLE")
        self.evidence_bucket = evidence_bucket or os.environ.get("S3_EVIDENCE_BUCKET")
        self.region = region or os.environ.get("AWS_REGION", self.DEFAULT_REGION)
        
        if not self.cases_table_name:
            raise ValueError("Cases table name required")
        if not self.evidence_bucket:
            raise ValueError("Evidence bucket name required")
        
        # Initialize AWS clients
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile)
            dynamodb = session.resource("dynamodb", region_name=self.region)
            self.s3_client = session.client("s3", region_name=self.region)
        else:
            dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self.s3_client = boto3.client("s3", region_name=self.region)
        
        self.cases_table = dynamodb.Table(self.cases_table_name)
        
        logger.info(
            f"Initialized CaseManager: table={self.cases_table_name}, "
            f"bucket={self.evidence_bucket}"
        )
    
    def create_case(
        self,
        decision_id: str,
        session_id: str,
        user_id: str,
        ai_action: str,
        ai_confidence: float,
        reason_for_review: str,
        evidence: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new review case.
        
        Args:
            decision_id: Original AI decision ID
            session_id: Session ID
            user_id: User ID
            ai_action: AI recommended action
            ai_confidence: AI confidence score
            reason_for_review: Why this needs review
            evidence: Evidence snapshot (will be stored in S3)
            metadata: Additional metadata
            
        Returns:
            Case ID
        """
        case_id = f"case_{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        
        # Store evidence snapshot in S3
        evidence_key = f"cases/{case_id}/evidence.json"
        try:
            self.s3_client.put_object(
                Bucket=self.evidence_bucket,
                Key=evidence_key,
                Body=json.dumps(evidence, indent=2, default=str).encode(),
                ContentType="application/json",
                Metadata={
                    "case-id": case_id,
                    "decision-id": decision_id,
                    "timestamp": now.isoformat(),
                },
            )
        except ClientError as e:
            logger.error(f"Failed to store evidence: {e}")
            raise
        
        # Create case record in DynamoDB
        case_item = {
            "pk": f"PK#CASE#{case_id}",
            "sk": f"SK#CASE#{now.isoformat()}",
            "case_id": case_id,
            "decision_id": decision_id,
            "session_id": session_id,
            "user_id": user_id,
            "status": CaseStatus.PENDING.value,
            "ai_action": ai_action,
            "ai_confidence": Decimal(str(ai_confidence)),
            "reason_for_review": reason_for_review,
            "evidence_uri": f"s3://{self.evidence_bucket}/{evidence_key}",
            "created_at": now.isoformat(),
            "history": [],
            "metadata": metadata or {},
            "gsi1_pk": f"CASE#PENDING",  # For querying pending cases
            "gsi1_sk": now.isoformat(),
            "gsi2_pk": f"USER#{user_id}",  # For querying user's cases
            "gsi2_sk": now.isoformat(),
        }
        
        try:
            self.cases_table.put_item(Item=case_item)
            logger.info(f"Created case: {case_id}")
            return case_id
        except ClientError as e:
            logger.error(f"Failed to create case: {e}")
            raise
    
    def add_review_action(
        self,
        case_id: str,
        action: ReviewAction,
        reviewer_id: str,
        reviewer_role: str,
        comment: Optional[str] = None,
        new_action: Optional[str] = None,
    ) -> bool:
        """Add a review action to a case.
        
        Args:
            case_id: Case ID
            action: Type of review action
            reviewer_id: Reviewer identifier
            reviewer_role: Reviewer role/title
            comment: Comment (required for OVERRIDE)
            new_action: New action (for OVERRIDE)
            
        Returns:
            True if successful
            
        Raises:
            ValueError: If validation fails
        """
        # Validate override has comment
        if action == ReviewAction.OVERRIDE and not comment:
            raise ValueError("Comment required when overriding decision")
        
        if action == ReviewAction.OVERRIDE and not new_action:
            raise ValueError("New action required when overriding decision")
        
        action_record = {
            "action": action.value,
            "reviewer_id": reviewer_id,
            "reviewer_role": reviewer_role,
            "comment": comment or "",
            "new_action": new_action or None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Determine new status
        new_status = {
            ReviewAction.APPROVE: CaseStatus.APPROVED.value,
            ReviewAction.REJECT: CaseStatus.REJECTED.value,
            ReviewAction.OVERRIDE: CaseStatus.OVERRIDDEN.value,
            ReviewAction.COMMENT: CaseStatus.IN_REVIEW.value,
            ReviewAction.DEFER: CaseStatus.DEFERRED.value,
            ReviewAction.ESCALATE: CaseStatus.ESCALATED.value,
        }[action]
        
        try:
            # Update case with new action and status
            self.cases_table.update_item(
                Key={
                    "pk": f"PK#CASE#{case_id}",
                    "sk": f"SK#CASE#",
                },
                UpdateExpression="SET #status = :status, #history = list_append(#history, :action), updated_at = :updated_at",
                ExpressionAttributeNames={
                    "#status": "status",
                    "#history": "history",
                },
                ExpressionAttributeValues={
                    ":status": new_status,
                    ":action": [action_record],
                    ":updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            
            logger.info(f"Added {action.value} to case {case_id}")
            return True
        
        except ClientError as e:
            logger.error(f"Failed to add review action: {e}")
            return False
    
    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Get case details.
        
        Args:
            case_id: Case ID
            
        Returns:
            Case record or None
        """
        try:
            response = self.cases_table.get_item(
                Key={
                    "pk": f"PK#CASE#{case_id}",
                    "sk": f"SK#CASE#",
                }
            )
            
            item = response.get("Item")
            if item:
                # Convert Decimal back to float
                if "ai_confidence" in item:
                    item["ai_confidence"] = float(item["ai_confidence"])
                return dict(item)
            
            return None
        
        except ClientError as e:
            logger.error(f"Failed to get case: {e}")
            return None
    
    def get_pending_cases(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get all pending review cases.
        
        Args:
            limit: Maximum results
            
        Returns:
            List of pending cases
        """
        try:
            response = self.cases_table.query(
                IndexName="gsi1_pk-gsi1_sk-index",
                KeyConditionExpression="gsi1_pk = :status",
                ExpressionAttributeValues={":status": f"CASE#{CaseStatus.PENDING.value}"},
                Limit=limit,
                ScanIndexForward=False,  # Most recent first
            )
            
            items = response.get("Items", [])
            for item in items:
                if "ai_confidence" in item:
                    item["ai_confidence"] = float(item["ai_confidence"])
            
            return [dict(item) for item in items]
        
        except ClientError as e:
            logger.error(f"Failed to get pending cases: {e}")
            return []
    
    def get_user_cases(
        self,
        user_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get all cases for a user.
        
        Args:
            user_id: User ID
            limit: Maximum results
            
        Returns:
            List of cases
        """
        try:
            response = self.cases_table.query(
                IndexName="gsi2_pk-gsi2_sk-index",
                KeyConditionExpression="gsi2_pk = :user_id",
                ExpressionAttributeValues={":user_id": f"USER#{user_id}"},
                Limit=limit,
                ScanIndexForward=False,
            )
            
            items = response.get("Items", [])
            for item in items:
                if "ai_confidence" in item:
                    item["ai_confidence"] = float(item["ai_confidence"])
            
            return [dict(item) for item in items]
        
        except ClientError as e:
            logger.error(f"Failed to get user cases: {e}")
            return []
    
    def get_evidence(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Get evidence snapshot for a case.
        
        Args:
            case_id: Case ID
            
        Returns:
            Evidence dictionary or None
        """
        evidence_key = f"cases/{case_id}/evidence.json"
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.evidence_bucket,
                Key=evidence_key,
            )
            evidence = json.loads(response["Body"].read().decode())
            return evidence
        
        except self.s3_client.exceptions.NoSuchKey:
            logger.warning(f"Evidence not found: {case_id}")
            return None
        except ClientError as e:
            logger.error(f"Failed to get evidence: {e}")
            return None
    
    def get_case_stats(self) -> Dict[str, Any]:
        """Get statistics about cases.
        
        Returns:
            Stats on pending, approved, overridden cases
        """
        try:
            stats = {}
            
            for status in CaseStatus:
                response = self.cases_table.query(
                    IndexName="gsi1_pk-gsi1_sk-index",
                    KeyConditionExpression="gsi1_pk = :status",
                    ExpressionAttributeValues={":status": f"CASE#{status.value}"},
                    Select="COUNT",
                )
                stats[status.value.lower()] = response.get("Count", 0)
            
            return stats
        
        except Exception as e:
            logger.error(f"Failed to get case stats: {e}")
            return {}


class ReviewUIBackend:
    """Backend for review UI operations.
    
    Provides:
    - Case listing
    - Evidence retrieval
    - Action submission
    - Review workflows
    """
    
    def __init__(self, case_manager: CaseManager):
        """Initialize UI backend.
        
        Args:
            case_manager: CaseManager instance
        """
        self.case_manager = case_manager
    
    def get_review_dashboard(self, reviewer_id: str) -> Dict[str, Any]:
        """Get dashboard data for a reviewer.
        
        Returns:
            - Pending cases count
            - Recent actions
            - Stats
        """
        pending = self.case_manager.get_pending_cases(limit=50)
        stats = self.case_manager.get_case_stats()
        
        return {
            "pending_count": len(pending),
            "pending_cases": pending[:10],  # Show first 10
            "stats": stats,
        }
    
    def submit_review(
        self,
        case_id: str,
        action: str,
        reviewer_id: str,
        reviewer_role: str,
        comment: Optional[str] = None,
        new_action: Optional[str] = None,
    ) -> bool:
        """Submit review action.
        
        Args:
            case_id: Case ID
            action: Action type (APPROVE, OVERRIDE, etc.)
            reviewer_id: Reviewer ID
            reviewer_role: Reviewer role
            comment: Optional comment
            new_action: New action for override
            
        Returns:
            True if successful
        """
        try:
            review_action = ReviewAction[action.upper()]
            return self.case_manager.add_review_action(
                case_id=case_id,
                action=review_action,
                reviewer_id=reviewer_id,
                reviewer_role=reviewer_role,
                comment=comment,
                new_action=new_action,
            )
        except KeyError:
            logger.error(f"Invalid action: {action}")
            return False
