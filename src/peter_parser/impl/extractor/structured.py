"""Structured LLM/VLM implementation for generating structured outputs."""
import asyncio
import json
import nest_asyncio
import base64
import instructor
import requests
from openai import AsyncOpenAI, AsyncAzureOpenAI
from pydantic import BaseModel

from typing import Dict, Any, List, Optional, get_origin, get_args

from peter_parser_core import BaseLLM, LLMError
from peter_parser.common.config import Config
from peter_parser.prompts.structured_output import (
    STRUCTURED_OUTPUT_SYSTEM_PROMPT,
    STRUCTURED_OUTPUT_PROMPT,
)


class StructuredLLM(BaseLLM):
    """Structured LLM/VLM for generating structured outputs.
    
    Supports both text-only (LLM) and vision (VLM) tasks using OpenAI.
    Automatically uses vision model when images are provided.
    """
    
    def __init__(self, datamodel: BaseModel, verbose: bool = False):
        """Initialize StructuredLLM.
        
        Args:
            datamodel: Pydantic model for structured output
            verbose: Enable verbose logging
        """
        self.datamodel = datamodel
        self.attribute_list = self.datamodel.model_fields.items()
        self.verbose = verbose
        
        # Initialize client(s) for OpenAI or OpenAI-compatible (vLLM, RunPod, Ollama)
        try:
            use_azure = (
                getattr(Config, "USE_AZURE", False)
                and getattr(Config, "AZURE_OPENAI_API_KEY", "")
            )
            if use_azure:
                client = AsyncAzureOpenAI(
                    api_key=Config.AZURE_OPENAI_API_KEY,
                    azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
                    api_version=Config.AZURE_API_VERSION,
                )
            else:
                client_kwargs = {"api_key": Config.OPENAI_API_KEY or "dummy"}
                if Config.OPENAI_BASE_URL:
                    client_kwargs["base_url"] = Config.OPENAI_BASE_URL
                client = AsyncOpenAI(**client_kwargs)
            # Mode.JSON: 모델이 content에 JSON을 반환할 때 사용 (tool_calls 미지원 시, e.g. Qwen)
            self.client = instructor.from_openai(client, mode=instructor.Mode.JSON)

            # VLM client (separate endpoint when LLM and VLM use different URLs)
            self.vlm_client = None
            if (
                Config.OPENAI_VISION_BASE_URL
                and Config.OPENAI_VISION_BASE_URL != Config.OPENAI_BASE_URL
            ):
                vlm_kwargs = {
                    "api_key": Config.OPENAI_API_KEY or "dummy",
                    "base_url": Config.OPENAI_VISION_BASE_URL,
                }
                self.vlm_client = instructor.from_openai(
                    AsyncOpenAI(**vlm_kwargs), mode=instructor.Mode.JSON
                )
        except Exception:
            client_kwargs = {"api_key": Config.OPENAI_API_KEY or "dummy"}
            if Config.OPENAI_BASE_URL:
                client_kwargs["base_url"] = Config.OPENAI_BASE_URL
            client = AsyncOpenAI(**client_kwargs)
            self.client = instructor.from_openai(client, mode=instructor.Mode.JSON)
            self.vlm_client = None
    
    def _get_structure_information(
        self,
        value_attr: str = "description",
        key_attr: str = "name"
    ) -> Dict[str, Any]:
        """Get structure information from datamodel."""
        result = {}
        for field_name, field_info in self.attribute_list:
            try:
                key = field_name if key_attr == "name" else getattr(field_info, key_attr, None)
                value = getattr(field_info, value_attr, None)
                if key is not None:
                    result[key] = {
                        'value': value,
                        'annotation': field_info.annotation
                    }
            except Exception as e:
                raise KeyError(f"Field '{field_name}' processing error: {e}") from e
        return result

    def _annotation_to_type_hint(self, annotation: Any) -> str:
        """Convert Pydantic/typing annotation to a short type hint for the prompt."""
        if get_origin(annotation) is list:
            args = get_args(annotation)
            if args and args[0] is str:
                return "array of strings"
            return "array"
        if annotation is str or (hasattr(annotation, "__name__") and annotation.__name__ == "str"):
            return "string"
        if annotation is int or (hasattr(annotation, "__name__") and annotation.__name__ == "int"):
            return "integer"
        if annotation is bool or (hasattr(annotation, "__name__") and annotation.__name__ == "bool"):
            return "boolean"
        if hasattr(annotation, "__name__"):
            return str(annotation.__name__).lower()
        return "value"

    def _format_structure_for_prompt(self, structure_info: Dict[str, Any]) -> str:
        """Format structure information as a flat JSON schema for the prompt.

        Describes each field as 'key (type): description' so the model outputs
        flat JSON (key -> value) instead of nested {value, annotation}.
        """
        lines = []
        for key, info in structure_info.items():
            if not isinstance(info, dict):
                continue
            desc = info.get("value") or ""
            ann = info.get("annotation")
            type_hint = self._annotation_to_type_hint(ann) if ann else "value"
            lines.append(f"- {key} ({type_hint}): {desc}")
        return "\n".join(lines) if lines else str(structure_info)

    def _prepare_image_data(self, image_data: bytes) -> str:
        """Prepare image data for OpenAI API.
        
        Args:
            image_data: Base64 encoded image bytes
        
        Returns:
            Data URL string
        """
        if isinstance(image_data, str):
            # Already base64 string
            return f"data:image/png;base64,{image_data}"
        else:
            # Bytes, encode to base64
            encoded = base64.b64encode(image_data).decode('utf-8')
            return f"data:image/png;base64,{encoded}"
    
    def _run_async(self, coro):
        """Run async coroutine safely, handling event loop properly."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                nest_asyncio.apply()
                return asyncio.run(coro)
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)
    
    async def generate(
        self,
        messages: List[Dict[str, Any]],
        response_model: type[BaseModel],
        **kwargs
    ) -> BaseModel:
        """BaseLLM interface implementation."""
        try:
            return await self.client.chat.completions.create(
                model=kwargs.get("model", Config.OPENAI_MODEL),
                messages=messages,
                response_model=response_model,
                temperature=kwargs.get("temperature", 0.0),
                max_tokens=kwargs.get("max_tokens", 2048),
            )
        except Exception as e:
            raise LLMError(f"OpenAI generation failed: {str(e)}") from e
    
    def structure_output(
        self,
        instruction: str,
        datamodel: Optional[type[BaseModel]] = None,
        images: Optional[List[bytes]] = None,
        user_system_prompt: str = " ",
        **kwargs
    ) -> BaseModel:
        """Generate structured output (sync).
        
        Args:
            instruction: Instruction text
            datamodel: Pydantic model for structured output (default: self.datamodel)
            images: Optional list of image data (base64 bytes or strings)
            user_system_prompt: System prompt (default: STRUCTURED_OUTPUT_SYSTEM_PROMPT)
            **kwargs: Additional options (model, temperature, etc.)
        
        Returns:
            Structured output matching datamodel
        """
        if datamodel is None:
            datamodel = self.datamodel
        
        system = (
            STRUCTURED_OUTPUT_SYSTEM_PROMPT
            if user_system_prompt == " "
            else user_system_prompt
        )
        structure_info = self._get_structure_information(**kwargs)
        user = STRUCTURED_OUTPUT_PROMPT.format(
            user_question=instruction,
            structure_information=self._format_structure_for_prompt(structure_info),
        )
        
        # Messages 구성
        messages = [{"role": "system", "content": system}]

        # Images가 있으면 vision 형식으로
        vlm_format = (Config.VLM_REQUEST_FORMAT or "openai").lower()
        if images:
            if vlm_format == "runpod":
                # RunPod: content 문자열 + image_base64 (첫 번째 이미지 사용)
                img_b64 = self._prepare_image_data(images[0])
                messages.append({
                    "role": "user",
                    "content": user,
                    "image_base64": img_b64,
                })
            else:
                # OpenAI: content 배열 + image_url
                content = [{"type": "text", "text": user}]
                for img_data in images:
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": self._prepare_image_data(img_data)},
                    })
                messages.append({"role": "user", "content": content})
            model = kwargs.get("model", Config.OPENAI_VISION_MODEL)
        else:
            messages.append({"role": "user", "content": user})
            model = kwargs.get("model", Config.OPENAI_MODEL)

        # Use VLM client when images present and VLM has separate endpoint
        api_client = (
            self.vlm_client if (images and self.vlm_client) else self.client
        )

        async def _async_call():
            return await api_client.chat.completions.create(
                model=model,
                messages=messages,
                response_model=datamodel,
                temperature=kwargs.get("temperature", 0.0),
                max_tokens=kwargs.get("max_tokens", 2048),
            )

        return self._run_async(_async_call())
    
    async def astructure_output(
        self,
        instruction: str,
        datamodel: Optional[type[BaseModel]] = None,
        images: Optional[List[bytes]] = None,
        user_system_prompt: str = " ",
        **kwargs
    ) -> BaseModel:
        """Generate structured output (async).
        
        Args:
            instruction: Instruction text
            datamodel: Pydantic model for structured output (default: self.datamodel)
            images: Optional list of image data (base64 bytes or strings)
            user_system_prompt: System prompt
            **kwargs: Additional options
        
        Returns:
            Structured output matching datamodel
        """
        if datamodel is None:
            datamodel = self.datamodel
        
        system = (
            STRUCTURED_OUTPUT_SYSTEM_PROMPT
            if user_system_prompt == " "
            else user_system_prompt
        )
        structure_info = self._get_structure_information(**kwargs)
        user = STRUCTURED_OUTPUT_PROMPT.format(
            user_question=instruction,
            structure_information=self._format_structure_for_prompt(structure_info),
        )
        
        # Messages 구성
        messages = [{"role": "system", "content": system}]

        # Images가 있으면 vision 형식으로
        vlm_format = (Config.VLM_REQUEST_FORMAT or "openai").lower()
        if images:
            if vlm_format == "runpod":
                # RunPod: content 문자열 + image_base64 (첫 번째 이미지 사용)
                img_b64 = self._prepare_image_data(images[0])
                messages.append({
                    "role": "user",
                    "content": user,
                    "image_base64": img_b64,
                })
            else:
                # OpenAI: content 배열 + image_url
                content = [{"type": "text", "text": user}]
                for img_data in images:
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": self._prepare_image_data(img_data)},
                    })
                messages.append({"role": "user", "content": content})
            model = kwargs.get("model", Config.OPENAI_VISION_MODEL)
        else:
            messages.append({"role": "user", "content": user})
            model = kwargs.get("model", Config.OPENAI_MODEL)

        api_client = (
            self.vlm_client if (images and self.vlm_client) else self.client
        )
        return await api_client.chat.completions.create(
            model=model,
            messages=messages,
            response_model=datamodel,
            temperature=kwargs.get("temperature", 0.0),
            max_tokens=kwargs.get("max_tokens", 2048),
        )

    async def astructure_output_batch(
        self,
        requests: List[Dict[str, Any]],
        datamodel: Optional[type[BaseModel]] = None,
        **kwargs
    ) -> List[BaseModel]:
        """Batch structured output via /v1/chat/completions/batch.

        Each item in requests must have: instruction, user_system_prompt (optional),
        key_attr, value_attr. Uses OPENAI_BATCH_URL when set.
        Returns list of parsed datamodel instances (or empty on failure).
        """
        if datamodel is None:
            datamodel = self.datamodel
        batch_url = getattr(Config, "OPENAI_BATCH_URL", None) or ""
        if not batch_url:
            raise ValueError("OPENAI_BATCH_URL not set; cannot use batch API")

        model = kwargs.get("model", Config.OPENAI_MODEL)
        max_tokens = kwargs.get("max_tokens", 2048)
        key_attr = kwargs.get("key_attr", "name")
        value_attr = kwargs.get("value_attr", "description")

        payload_requests: List[Dict[str, Any]] = []
        for req in requests:
            instruction = req.get("instruction", "")
            user_system_prompt = req.get("user_system_prompt", " ")
            system = (
                STRUCTURED_OUTPUT_SYSTEM_PROMPT
                if user_system_prompt == " "
                else user_system_prompt
            )
            structure_info = self._get_structure_information(
                key_attr=req.get("key_attr", key_attr),
                value_attr=req.get("value_attr", value_attr),
            )
            user = STRUCTURED_OUTPUT_PROMPT.format(
                user_question=instruction,
                structure_information=self._format_structure_for_prompt(structure_info),
            )
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
            payload_requests.append({
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
            })

        batch_data = {"requests": payload_requests}
        headers = {
            "Authorization": f"Bearer {Config.OPENAI_API_KEY or 'dummy'}",
            "Content-Type": "application/json",
        }

        def _sync_post():
            return requests.post(
                batch_url,
                json=batch_data,
                headers=headers,
                timeout=600,
            )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _sync_post)
        response.raise_for_status()
        result = response.json()

        responses = result.get("responses", [])
        outputs: List[BaseModel] = []
        for i, resp in enumerate(responses):
            try:
                content = ""
                if isinstance(resp, dict):
                    choices = resp.get("choices", [])
                    if choices:
                        msg = choices[0].get("message", {})
                        content = msg.get("content", "") or ""
                if not content:
                    outputs.append(datamodel())
                    continue
                raw = json.loads(content) if isinstance(content, str) else content
                outputs.append(datamodel.model_validate(raw))
            except Exception:
                outputs.append(datamodel())
        return outputs