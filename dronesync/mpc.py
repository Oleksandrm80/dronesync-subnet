"""
DroneSync - Multi-Party Computation
Validators jointly verify PoPW without seeing full flight data.
"""
import hashlib
import secrets
import time


PRIME = 2**127 - 1


def _commitment(validator_id: str, x: int, value: float) -> str:
    data = f"{validator_id}:{x}:{value}".encode()
    return hashlib.sha256(data).hexdigest()


class SecretShare:
    def __init__(self, validator_id: str, x: int, y: int, commitment: str):
        self.validator_id = validator_id
        self.x = x
        self.y = y
        self.commitment = commitment

    def to_tuple(self):
        return (self.x, self.y)


class ShamirSecretSharing:
    def __init__(self, threshold: int = 2, n_shares: int = 3):
        if threshold > n_shares:
            raise ValueError(f"threshold={threshold} cannot exceed n_shares={n_shares}")
        self.threshold = threshold
        self.n_shares = n_shares

    def _poly_eval(self, coeffs: list, x: int) -> int:
        result = 0
        for coeff in reversed(coeffs):
            result = (result * x + coeff) % PRIME
        return result

    def split(self, secret: float) -> list:
        secret_int = int(secret * 1_000_000)
        coeffs = [secret_int] + [
            secrets.randbelow(PRIME) for _ in range(self.threshold - 1)
        ]
        shares = []
        for x in range(1, self.n_shares + 1):
            y = self._poly_eval(coeffs, x)
            shares.append((x, y))
        return shares

    def reconstruct(self, shares: list) -> float:
        if len(shares) < self.threshold:
            raise ValueError(f"Need {self.threshold} shares, got {len(shares)}")

        def mod_inv(a, p):
            return pow(a, p - 2, p)

        secret_int = 0
        for i, (xi, yi) in enumerate(shares):
            num = yi
            den = 1
            for j, (xj, _) in enumerate(shares):
                if i != j:
                    num = (num * (-xj)) % PRIME
                    den = (den * (xi - xj)) % PRIME
            secret_int = (secret_int + num * mod_inv(den, PRIME)) % PRIME

        return secret_int / 1_000_000


class MPCResult:
    def __init__(self, mission_id: str, accepted: bool, reconstructed_score: float,
                 shares_used: int, validators: list):
        self.mission_id = mission_id
        self.accepted = accepted
        self.reconstructed_score = reconstructed_score
        self.shares_used = shares_used
        self.validators = validators
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "accepted": self.accepted,
            "reconstructed_score": round(self.reconstructed_score, 4),
            "shares_used": self.shares_used,
            "validators": self.validators,
            "timestamp": self.timestamp,
        }


class MPCCoordinator:
    def __init__(self, validator_ids: list, threshold: int = 2):
        self.validator_ids = validator_ids
        self.threshold = threshold
        self.n = len(validator_ids)
        self.sss = ShamirSecretSharing(threshold=threshold, n_shares=self.n)

    def split_popw(self, popw: dict) -> dict:
        score = popw.get("score", 0.0)
        shares = self.sss.split(score)
        result = {}
        for i, val_id in enumerate(self.validator_ids):
            x, y = shares[i]
            commit = _commitment(val_id, x, score)
            result[val_id] = SecretShare(val_id, x, y, commit)
        return result

    def validate_popw_private(self, popw: dict, min_score: float = 60.0) -> MPCResult:
        shares_dict = self.split_popw(popw)
        threshold_shares = [
            shares_dict[v].to_tuple()
            for v in self.validator_ids[:self.threshold]
        ]
        reconstructed = self.sss.reconstruct(threshold_shares)
        accepted = reconstructed >= min_score
        return MPCResult(
            mission_id=popw.get("mission_id", ""),
            accepted=accepted,
            reconstructed_score=reconstructed,
            shares_used=self.threshold,
            validators=self.validator_ids[:self.threshold],
        )

    def reconstruct_and_validate(self, shares_dict: dict, mission_id: str,
                                  min_score: float = 60.0) -> MPCResult:
        shares = [s.to_tuple() for s in shares_dict.values()]
        accepted = False
        reconstructed = 0.0
        if len(shares) >= self.threshold:
            try:
                reconstructed = self.sss.reconstruct(shares[:self.threshold])
                accepted = reconstructed >= min_score
            except ValueError:
                pass
        return MPCResult(
            mission_id=mission_id,
            accepted=accepted,
            reconstructed_score=reconstructed,
            shares_used=len(shares),
            validators=list(shares_dict.keys()),
        )


class MPCVerifier:
    def __init__(self, validator_ids: list, threshold: int = 2):
        self.validator_ids = validator_ids
        self.threshold = threshold
        self.n = len(validator_ids)
        self.sss = ShamirSecretSharing(threshold=threshold, n_shares=self.n)

    def distribute_popw(self, popw: dict) -> dict:
        score = popw.get("score", 0.0)
        mission_id = popw.get("mission_id", "")
        trajectory_hash = popw.get("trajectory_hash", "")
        shares = self.sss.split(score)
        commit_hash = hashlib.sha256(
            f"{mission_id}:{trajectory_hash}:{score}".encode()
        ).hexdigest()
        return {
            "mission_id": mission_id,
            "commit_hash": commit_hash,
            "threshold": self.threshold,
            "total_validators": self.n,
            "shares": {
                self.validator_ids[i]: {"share": shares[i], "validator_id": self.validator_ids[i]}
                for i in range(self.n)
            },
            "timestamp": time.time(),
        }

    def collect_and_verify(self, distribution: dict, responding_validators: list) -> dict:
        if len(responding_validators) < self.threshold:
            return {
                "valid": False,
                "reason": "insufficient_shares",
                "shares_received": len(responding_validators),
                "threshold": self.threshold,
            }
        shares = []
        for val_id in responding_validators[:self.threshold]:
            share_data = distribution["shares"].get(val_id)
            if share_data:
                shares.append(share_data["share"])
        if len(shares) < self.threshold:
            return {"valid": False, "reason": "invalid_validators"}
        reconstructed_score = self.sss.reconstruct(shares)
        valid = reconstructed_score >= 0.6
        return {
            "valid": valid,
            "reconstructed_score": round(reconstructed_score, 4),
            "shares_used": len(shares),
            "mission_id": distribution["mission_id"],
            "commit_hash": distribution["commit_hash"],
            "timestamp": time.time(),
        }
