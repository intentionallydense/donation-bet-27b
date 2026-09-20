"""CPU integration check using a tiny random hybrid Qwen, not the 27B weights."""
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from probe import forward


class RuntimeTests(unittest.TestCase):
    def test_hybrid_hooks_are_causal_and_before_final_norm(self):
        import torch
        from transformers import Qwen3_5TextConfig, Qwen3_5TextModel
        torch.manual_seed(123)
        config = Qwen3_5TextConfig(
            vocab_size=64, hidden_size=32, intermediate_size=64,
            num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=1,
            head_dim=16, layer_types=['linear_attention','full_attention'],
            linear_key_head_dim=8, linear_value_head_dim=8,
            linear_num_key_heads=2, linear_num_value_heads=2,
            max_position_embeddings=128, partial_rotary_factor=.5,
            rope_parameters={'rope_type':'default','rope_theta':10000.,
                             'partial_rotary_factor':.5,'mrope_section':[1,1,2]})
        decoder = Qwen3_5TextModel(config).eval()
        captured = {}
        forward(torch,decoder,[1,2,3,4,5],[0,1],lambda layer,h: captured.update({layer:h.cpu().numpy().copy()}))
        self.assertEqual(captured[0].shape,(5,32))
        other = {}
        forward(torch,decoder,[1,2,3,9,10],[0,1],lambda layer,h: other.update({layer:h.cpu().numpy().copy()}))
        for layer in (0,1):
            np.testing.assert_allclose(captured[layer][:3],other[layer][:3],atol=1e-6)
            self.assertEqual(len(decoder.layers[layer]._forward_hooks),0)
        with torch.inference_mode():
            result = decoder(input_ids=torch.tensor([[1,2,3,4,5]]),use_cache=False).last_hidden_state
            expected = decoder.norm(torch.tensor(captured[1]))
        torch.testing.assert_close(result[0],expected)

if __name__ == '__main__':
    unittest.main()
