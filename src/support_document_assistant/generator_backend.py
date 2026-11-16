"""One explicitly selected local Qwen CPU backend; no external or model fallback."""
import json
import os
from pathlib import Path
from .assets import sha256
from .generator_assets import model_directory


class QwenTokenizer:
    def __init__(self, root, config):
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        from transformers import AutoTokenizer
        directory = model_directory(root, weights=False)
        self.tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True,
                                                       trust_remote_code=False, use_fast=True)
        if not self.tokenizer.is_fast:
            raise ValueError("Fast Qwen tokenizer required; no slow fallback")
        self.tokenizer.backend_tokenizer.no_truncation()
        self.tokenizer.backend_tokenizer.no_padding()
        if sha256(self.tokenizer.chat_template.encode()) != config["chat_template_sha256"]:
            raise ValueError("Official Qwen chat template changed")
        actual = json.loads((directory / "config.json").read_bytes())["max_position_embeddings"]
        if actual != config["model_max_position_embeddings"] or config["context_total_tokens"] > actual:
            raise ValueError("Configured prompt budget exceeds verified model capacity")
        self.config = config

    def format(self, messages):
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        ids = self.tokenizer(text, add_special_tokens=False, truncation=False,
                             padding=False, verbose=False)["input_ids"]
        return text, ids


class QwenGenerator(QwenTokenizer):
    def __init__(self, root, config):
        import torch
        from transformers import AutoModelForCausalLM, GenerationConfig
        if torch.version.cuda is not None:
            raise ValueError("CPU-only PyTorch is required")
        torch.set_num_threads(config["torch_intra_op_threads"])
        if torch.get_num_interop_threads() != config["torch_inter_op_threads"]:
            torch.set_num_interop_threads(config["torch_inter_op_threads"])
        torch.use_deterministic_algorithms(True)
        torch.manual_seed(config["seed"])
        super().__init__(root, config)
        directory = model_directory(root)
        self.model = AutoModelForCausalLM.from_pretrained(directory, local_files_only=True,
            trust_remote_code=False, use_safetensors=True, dtype=torch.bfloat16,
            attn_implementation=config["attention"]).eval()
        if (any(p.device.type != "cpu" or p.dtype != torch.bfloat16 for p in self.model.parameters())
                or self.model.config.max_position_embeddings != config["model_max_position_embeddings"]):
            raise ValueError("Actual model device, precision or capacity differs from specification")
        self.generation_config = GenerationConfig(**config["generation"])
        self.torch = torch

    def generate(self, context):
        text, ids = self.format(context["messages"])
        if (text != context["formatted_prompt"] or ids != context["input_token_ids"]
                or len(ids) + self.config["output_token_cap"] > self.config["context_total_tokens"]):
            raise ValueError("Complete formatted prompt changed or exceeds budget; not truncated")
        tensor = self.torch.tensor([ids], dtype=self.torch.long, device="cpu")
        with self.torch.inference_mode():
            output = self.model.generate(input_ids=tensor, attention_mask=self.torch.ones_like(tensor),
                generation_config=self.generation_config, logits_to_keep=1)
        generated = output[0, len(ids):].tolist()
        if not generated or len(generated) > self.config["output_token_cap"]:
            raise ValueError("Unexpected generated token shape")
        eos = generated[-1] in self.config["generation"]["eos_token_id"]
        return {"raw_output": self.tokenizer.decode(generated, skip_special_tokens=True,
                                                   clean_up_tokenization_spaces=False),
                "generated_token_ids": generated, "output_tokens": len(generated),
                "ended_with_eos": eos,
                "reached_cap_without_eos": len(generated) == self.config["output_token_cap"] and not eos}

    def description(self):
        return {"model_class": type(self.model).__name__, "tokenizer_class": type(self.tokenizer).__name__,
            "device": str(next(self.model.parameters()).device), "precision": str(next(self.model.parameters()).dtype),
            "parameter_count": sum(p.numel() for p in self.model.parameters()),
            "attention": self.model.config._attn_implementation,
            "model_position_limit": self.model.config.max_position_embeddings,
            "tokenizer_declared_limit": self.tokenizer.model_max_length,
            "application_total_token_cap": self.config["context_total_tokens"],
            "torch_cuda_version": self.torch.version.cuda,
            "torch_intra_op_threads": self.torch.get_num_threads(),
            "torch_inter_op_threads": self.torch.get_num_interop_threads(),
            "chat_template_sha256": sha256(self.tokenizer.chat_template.encode()),
            "generation_config": self.generation_config.to_diff_dict()}
