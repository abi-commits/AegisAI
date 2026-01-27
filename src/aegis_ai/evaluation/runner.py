"""Evaluation Runner - Prove the System Works.

Run realistic scenarios and measure what matters:
- 100 legitimate logins
- 20 ATO scenarios
- Print results. No dashboards yet.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.aegis_ai.evaluation.metrics import EvaluationMetrics
from src.aegis_ai.data.generators.legit_login import LegitLoginGenerator
from src.aegis_ai.data.generators.ato_login import ATOLoginGenerator
from src.aegis_ai.data.schemas import User, Device, Session, LoginEvent
from src.aegis_ai.orchestration.decision_context import InputContext
from src.aegis_ai.orchestration.decision_flow import DecisionFlow


class EvaluationRunner:
    """Runs evaluation scenarios and collects metrics."""
    
    def __init__(self, seed: int = 42):
        """Initialize runner with deterministic seed."""
        self.seed = seed
        self.legit_generator = LegitLoginGenerator(seed=seed)
        self.ato_generator = ATOLoginGenerator(seed=seed + 1000)  # Different seed
        self.decision_flow = DecisionFlow()
        self.metrics = EvaluationMetrics()
    
    def reset(self) -> None:
        """Reset all state for fresh run."""
        self.legit_generator.reset()
        self.ato_generator.reset()
        self.metrics = EvaluationMetrics()
    
    def run_evaluation(
        self,
        num_legit: int = 100,
        num_ato: int = 20,
        verbose: bool = True
    ) -> EvaluationMetrics:
        """Run full evaluation suite.
        
        Args:
            num_legit: Number of legitimate login scenarios
            num_ato: Number of ATO scenarios
            verbose: Print progress
            
        Returns:
            EvaluationMetrics with all results
        """
        self.reset()
        
        if verbose:
            print("\n🚀 Starting AegisAI Evaluation...")
            print(f"   Legitimate logins: {num_legit}")
            print(f"   ATO scenarios:     {num_ato}")
            print()
        
        # Run legitimate logins
        if verbose:
            print("📗 Processing legitimate logins...")
        
        base_time = datetime.now(timezone.utc) - timedelta(days=7)
        legit_processed = 0
        
        for i in range(num_legit):
            try:
                user = self.legit_generator.generate_user()
                scenarios = self.legit_generator.generate_legit_scenario(
                    user=user,
                    base_time=base_time + timedelta(hours=i),
                    num_events=1
                )
                
                for session, device, login_event in scenarios:
                    result = self._process_event(
                        user=user,
                        device=device,
                        session=session,
                        login_event=login_event,
                        is_ato=False
                    )
                    legit_processed += 1
                    
                    if verbose and legit_processed % 25 == 0:
                        print(f"   Processed {legit_processed}/{num_legit} legit logins...")
                        
            except Exception as e:
                if verbose:
                    print(f"   ⚠️  Error processing legit login {i}: {e}")
        
        if verbose:
            print(f"   ✓ Completed {legit_processed} legitimate logins\n")
        
        # Run ATO scenarios
        if verbose:
            print("📕 Processing ATO scenarios...")
        
        ato_processed = 0
        
        for i in range(num_ato):
            try:
                # Create a victim user (established account)
                user = self.ato_generator.generate_user()
                
                # Generate ATO attack
                scenarios = self.ato_generator.generate_ato_scenario(
                    user=user,
                    base_time=base_time + timedelta(hours=i + num_legit),
                )
                
                # We only need to evaluate the "successful" attack attempt
                # (the one that would get past basic auth)
                for session, device, login_event in scenarios:
                    if login_event.success:  # Only evaluate successful auth attempts
                        result = self._process_event(
                            user=user,
                            device=device,
                            session=session,
                            login_event=login_event,
                            is_ato=True
                        )
                        ato_processed += 1
                        break  # One event per scenario is enough
                
                if verbose and (i + 1) % 5 == 0:
                    print(f"   Processed {i + 1}/{num_ato} ATO scenarios...")
                    
            except Exception as e:
                if verbose:
                    print(f"   ⚠️  Error processing ATO scenario {i}: {e}")
        
        if verbose:
            print(f"   ✓ Completed {ato_processed} ATO scenarios\n")
        
        return self.metrics
    
    def _process_event(
        self,
        user: User,
        device: Device,
        session: Session,
        login_event: LoginEvent,
        is_ato: bool
    ) -> dict:
        """Process a single login event through the decision flow."""
        # Create input context
        input_context = InputContext(
            login_event=login_event,
            session=session,
            device=device,
            user=user
        )
        
        # Run through decision flow
        decision_context = self.decision_flow.process(input_context)
        
        # Extract results
        decision = decision_context.final_decision
        
        if decision is None:
            # This shouldn't happen, but handle gracefully
            return {"error": "No decision made"}
        
        # Record result
        self.metrics.add_result(
            is_ato=is_ato,
            action=decision.action,
            decided_by=decision.decided_by,
            confidence=decision.confidence_score,
            had_policy_violation=False,  # TODO: Track from policy engine
            was_overridden=False  # No human override in automated evaluation
        )
        
        return {
            "action": decision.action,
            "decided_by": decision.decided_by,
            "confidence": decision.confidence_score,
            "is_ato": is_ato,
        }


def run_standard_evaluation() -> EvaluationMetrics:
    """Run the standard evaluation: 100 legit + 20 ATO."""
    runner = EvaluationRunner(seed=42)
    metrics = runner.run_evaluation(
        num_legit=100,
        num_ato=20,
        verbose=True
    )
    metrics.print_report()
    return metrics


def run_quick_evaluation() -> EvaluationMetrics:
    """Run a quick evaluation: 20 legit + 5 ATO."""
    runner = EvaluationRunner(seed=42)
    metrics = runner.run_evaluation(
        num_legit=20,
        num_ato=5,
        verbose=True
    )
    metrics.print_report()
    return metrics


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run AegisAI evaluation")
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Run quick evaluation (20 legit + 5 ATO)"
    )
    parser.add_argument(
        "--legit", "-l",
        type=int,
        default=100,
        help="Number of legitimate logins (default: 100)"
    )
    parser.add_argument(
        "--ato", "-a",
        type=int,
        default=20,
        help="Number of ATO scenarios (default: 20)"
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    
    args = parser.parse_args()
    
    if args.quick:
        run_quick_evaluation()
    else:
        runner = EvaluationRunner(seed=args.seed)
        metrics = runner.run_evaluation(
            num_legit=args.legit,
            num_ato=args.ato,
            verbose=True
        )
        metrics.print_report()
