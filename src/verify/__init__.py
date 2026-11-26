"""Verificador independiente de las restricciones obligatorias."""

from .verifier import RULES, VerificationResult, Violation, verify_solution

__all__ = ["RULES", "VerificationResult", "Violation", "verify_solution"]
