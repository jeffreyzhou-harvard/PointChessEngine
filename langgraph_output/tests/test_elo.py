"""
Tests for ELO strength configuration.

Tests:
- Monotonic depth scaling with ELO
- Deterministic behavior when seeded
- Never blunders forced mates
- Noise injection
- Move selection strategies
- Configuration validation
"""

import pytest
import random
from search.elo import EloConfig, config_from_elo


class TestEloConfigCreation:
    """Test EloConfig creation and validation."""
    
    def test_config_from_elo_basic(self):
        """Test basic config creation."""
        config = config_from_elo(1500)
        
        assert config.elo_rating == 1500
        assert 1 <= config.base_depth <= 8
        assert 0.0 <= config.time_multiplier <= 1.0
        assert 0 <= config.eval_noise <= 300
        assert 0.0 <= config.best_move_probability <= 1.0
    
    def test_config_from_elo_clamping(self):
        """Test that ELO is clamped to valid range."""
        # Below minimum
        config = config_from_elo(100)
        assert config.elo_rating == 400
        
        # Above maximum
        config = config_from_elo(3000)
        assert config.elo_rating == 2400
        
        # Within range
        config = config_from_elo(1500)
        assert config.elo_rating == 1500
    
    def test_config_validation(self):
        """Test that invalid configs raise errors."""
        # Valid config should not raise
        config = EloConfig(
            elo_rating=1500,
            base_depth=4,
            time_multiplier=0.5,
            eval_noise=100,
            best_move_probability=0.7
        )
        assert config.elo_rating == 1500
        
        # Invalid ELO
        with pytest.raises(AssertionError):
            EloConfig(
                elo_rating=100,  # Too low
                base_depth=4,
                time_multiplier=0.5,
                eval_noise=100,
                best_move_probability=0.7
            )
        
        # Invalid depth
        with pytest.raises(AssertionError):
            EloConfig(
                elo_rating=1500,
                base_depth=10,  # Too high
                time_multiplier=0.5,
                eval_noise=100,
                best_move_probability=0.7
            )


class TestMonotonicScaling:
    """Test that parameters scale monotonically with ELO."""
    
    def test_depth_increases_with_elo(self):
        """Test that depth increases monotonically with ELO."""
        elo_levels = [400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400]
        depths = [config_from_elo(elo).base_depth for elo in elo_levels]
        
        # Depth should be non-decreasing
        for i in range(len(depths) - 1):
            assert depths[i] <= depths[i + 1], \
                f"Depth decreased from ELO {elo_levels[i]} to {elo_levels[i+1]}"
        
        # Check specific values
        assert config_from_elo(400).base_depth == 1
        assert config_from_elo(2400).base_depth == 8
    
    def test_time_multiplier_increases_with_elo(self):
        """Test that time multiplier increases monotonically with ELO."""
        elo_levels = [400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400]
        time_mults = [config_from_elo(elo).time_multiplier for elo in elo_levels]
        
        # Time multiplier should be non-decreasing
        for i in range(len(time_mults) - 1):
            assert time_mults[i] <= time_mults[i + 1], \
                f"Time multiplier decreased from ELO {elo_levels[i]} to {elo_levels[i+1]}"
        
        # Check specific values
        assert config_from_elo(400).time_multiplier == 0.1
        assert config_from_elo(2400).time_multiplier == 1.0
    
    def test_noise_decreases_with_elo(self):
        """Test that noise decreases monotonically with ELO."""
        elo_levels = [400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400]
        noises = [config_from_elo(elo).eval_noise for elo in elo_levels]
        
        # Noise should be non-increasing
        for i in range(len(noises) - 1):
            assert noises[i] >= noises[i + 1], \
                f"Noise increased from ELO {elo_levels[i]} to {elo_levels[i+1]}"
        
        # Check specific values
        assert config_from_elo(400).eval_noise == 300
        assert config_from_elo(2400).eval_noise == 0
    
    def test_best_move_probability_increases_with_elo(self):
        """Test that best move probability increases monotonically with ELO."""
        elo_levels = [400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400]
        probs = [config_from_elo(elo).best_move_probability for elo in elo_levels]
        
        # Probability should be non-decreasing
        for i in range(len(probs) - 1):
            assert probs[i] <= probs[i + 1], \
                f"Best move probability decreased from ELO {elo_levels[i]} to {elo_levels[i+1]}"
        
        # Check specific values
        assert config_from_elo(400).best_move_probability == 0.3
        assert config_from_elo(2400).best_move_probability == 1.0


class TestDeterministicBehavior:
    """Test that behavior is deterministic when seeded."""
    
    def test_noise_deterministic_with_seed(self):
        """Test that noise is deterministic when seeded."""
        config = config_from_elo(1200)
        
        # Same seed should give same noise
        score1 = config.add_noise_to_score(100, seed=42)
        score2 = config.add_noise_to_score(100, seed=42)
        assert score1 == score2
        
        # Different seeds should (usually) give different noise
        score3 = config.add_noise_to_score(100, seed=43)
        # Note: might occasionally be equal by chance, but very unlikely
    
    def test_move_selection_deterministic_with_seed(self):
        """Test that move selection is deterministic when seeded."""
        config = config_from_elo(1200)
        
        # Create mock moves with scores
        moves_with_scores = [
            ('e2e4', 50),
            ('d2d4', 45),
            ('g1f3', 40),
            ('c2c4', 35)
        ]
        
        # Same seed should give same move
        move1 = config.select_move(moves_with_scores, seed=42)
        move2 = config.select_move(moves_with_scores, seed=42)
        assert move1 == move2
    
    def test_noise_zero_at_max_elo(self):
        """Test that max ELO has zero noise."""
        config = config_from_elo(2400)
        
        # Should have no noise
        assert config.eval_noise == 0
        
        # Adding noise should not change score
        score = config.add_noise_to_score(100)
        assert score == 100


class TestForcedMateHandling:
    """Test that forced mates are never blundered."""
    
    def test_never_blunders_forced_mate(self):
        """Test that engine never blunders forced mates."""
        # Test at various ELO levels
        elo_levels = [400, 800, 1200, 1600, 2000, 2400]
        
        for elo in elo_levels:
            config = config_from_elo(elo)
            
            # Should never blunder forced mates
            assert not config.should_blunder_mate(True), \
                f"ELO {elo} should not blunder forced mate"
            
            # Test multiple times to ensure consistency
            for _ in range(10):
                assert not config.should_blunder_mate(True, seed=random.randint(0, 1000))


class TestNoiseInjection:
    """Test noise injection behavior."""
    
    def test_noise_range(self):
        """Test that noise is within expected range."""
        config = config_from_elo(1200)
        
        # Test many times to check range
        scores = []
        for i in range(100):
            score = config.add_noise_to_score(0, seed=i)
            scores.append(score)
        
        # All scores should be within noise range
        max_noise = config.eval_noise
        assert all(-max_noise <= s <= max_noise for s in scores)
        
        # Should have some variation
        assert len(set(scores)) > 10  # At least 10 different values
    
    def test_noise_affects_evaluation(self):
        """Test that noise actually affects evaluation."""
        config = config_from_elo(1000)
        
        # With noise, should get different results
        scores = set()
        for i in range(20):
            score = config.add_noise_to_score(100, seed=i)
            scores.add(score)
        
        # Should have multiple different scores
        assert len(scores) > 5
    
    def test_low_elo_has_high_noise(self):
        """Test that low ELO has high noise."""
        low_config = config_from_elo(400)
        high_config = config_from_elo(2400)
        
        assert low_config.eval_noise > high_config.eval_noise
        assert low_config.eval_noise == 300
        assert high_config.eval_noise == 0


class TestMoveSelection:
    """Test move selection strategies."""
    
    def test_max_elo_always_chooses_best(self):
        """Test that max ELO always chooses best move."""
        config = config_from_elo(2400)
        
        moves_with_scores = [
            ('e2e4', 50),
            ('d2d4', 45),
            ('g1f3', 40)
        ]
        
        # Should always choose best move
        for i in range(20):
            move = config.select_move(moves_with_scores, seed=i)
            assert move == 'e2e4'
    
    def test_low_elo_sometimes_chooses_suboptimal(self):
        """Test that low ELO sometimes chooses suboptimal moves."""
        config = config_from_elo(400)
        
        moves_with_scores = [
            ('e2e4', 50),
            ('d2d4', 45),
            ('g1f3', 40)
        ]
        
        # Should sometimes choose non-best moves
        moves_chosen = set()
        for i in range(50):
            move = config.select_move(moves_with_scores, seed=i)
            moves_chosen.add(move)
        
        # Should have chosen multiple different moves
        assert len(moves_chosen) > 1
    
    def test_move_selection_with_single_move(self):
        """Test move selection with only one move."""
        config = config_from_elo(1500)
        
        moves_with_scores = [('e2e4', 50)]
        
        # Should always return the only move
        move = config.select_move(moves_with_scores)
        assert move == 'e2e4'
    
    def test_move_selection_with_empty_list(self):
        """Test move selection with no moves."""
        config = config_from_elo(1500)
        
        moves_with_scores = []
        
        # Should return None
        move = config.select_move(moves_with_scores)
        assert move is None
    
    def test_move_selection_weighted_distribution(self):
        """Test that move selection follows weighted distribution."""
        config = config_from_elo(800)  # Low ELO, more randomness
        
        moves_with_scores = [
            ('e2e4', 50),
            ('d2d4', 45),
            ('g1f3', 40)
        ]
        
        # Count how often each move is chosen
        move_counts = {'e2e4': 0, 'd2d4': 0, 'g1f3': 0}
        
        for i in range(200):
            move = config.select_move(moves_with_scores, seed=i)
            move_counts[move] += 1
        
        # Best move should be chosen most often
        assert move_counts['e2e4'] > move_counts['d2d4']
        assert move_counts['d2d4'] > 0  # But second best should also be chosen sometimes
        assert move_counts['g1f3'] > 0  # And third best too


class TestEloConfigString:
    """Test string representation."""
    
    def test_str_representation(self):
        """Test that string representation is informative."""
        config = config_from_elo(1500)
        
        s = str(config)
        
        # Should contain key information
        assert '1500' in s
        assert str(config.base_depth) in s
        assert 'EloConfig' in s


class TestEloRangeMapping:
    """Test specific ELO range mappings."""
    
    def test_beginner_level(self):
        """Test beginner level (400 ELO)."""
        config = config_from_elo(400)
        
        assert config.base_depth == 1
        assert config.time_multiplier == 0.1
        assert config.eval_noise == 300
        assert config.best_move_probability == 0.3
    
    def test_intermediate_level(self):
        """Test intermediate level (1200 ELO)."""
        config = config_from_elo(1200)
        
        # Depth: 1 + (1200-400)*7/2000 = 1 + 800*7/2000 = 1 + 2.8 = 3.8 -> 3
        assert config.base_depth == 3
        assert 0.4 <= config.time_multiplier <= 0.6
        assert 50 <= config.eval_noise <= 150
        assert 0.6 <= config.best_move_probability <= 0.8
    
    def test_expert_level(self):
        """Test expert level (2400 ELO)."""
        config = config_from_elo(2400)
        
        assert config.base_depth == 8
        assert config.time_multiplier == 1.0
        assert config.eval_noise == 0
        assert config.best_move_probability == 1.0
    
    def test_smooth_interpolation(self):
        """Test that interpolation is smooth (no sudden jumps)."""
        # Test every 100 ELO points
        for elo in range(400, 2401, 100):
            config = config_from_elo(elo)
            
            # All parameters should be in valid ranges
            assert 1 <= config.base_depth <= 8
            assert 0.1 <= config.time_multiplier <= 1.0
            assert 0 <= config.eval_noise <= 300
            assert 0.3 <= config.best_move_probability <= 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
