"""Structured LLM/VLM implementation for generating structured outputs."""
import asyncio
import nest_asyncio
import base64
import instructor
from openai import AsyncOpenAI, AsyncAzureOpenAI
from pydantic import BaseModel

from typing import Dict, Any, List, Optional

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
        
        # Initialize client
        try:
            if Config.USE_AZURE and Config.AZURE_OPENAI_API_KEY:
                client = AsyncAzureOpenAI(
                    api_key=Config.AZURE_OPENAI_API_KEY,
                    azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
                    api_version=Config.AZURE_API_VERSION,
                )
            else:
                client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
            self.client = instructor.from_openai(client)
        except Exception:
            client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
            self.client = instructor.from_openai(client)
    
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
        user = STRUCTURED_OUTPUT_PROMPT.format(
            user_question=instruction,
            structure_information=self._get_structure_information(**kwargs)
        )
        
        # Messages 구성
        messages = [{"role": "system", "content": system}]
        
        # Images가 있으면 vision 형식으로
        if images:
            content = [{"type": "text", "text": user}]
            for img_data in images:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": self._prepare_image_data(img_data)
                    }
                })
            messages.append({"role": "user", "content": content})
            # Vision 모델 사용
            model = kwargs.get("model", Config.OPENAI_VISION_MODEL)
        else:
            messages.append({"role": "user", "content": user})
            model = kwargs.get("model", Config.OPENAI_MODEL)
        
        # 비동기 호출을 동기적으로 실행
        async def _async_call():
            return await self.client.chat.completions.create(
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
        user = STRUCTURED_OUTPUT_PROMPT.format(
            user_question=instruction,
            structure_information=self._get_structure_information(**kwargs)
        )
        
        # Messages 구성
        messages = [{"role": "system", "content": system}]
        
        # Images가 있으면 vision 형식으로
        if images:
            content = [{"type": "text", "text": user}]
            for img_data in images:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": self._prepare_image_data(img_data)
                    }
                })
            messages.append({"role": "user", "content": content})
            model = kwargs.get("model", Config.OPENAI_VISION_MODEL)
        else:
            messages.append({"role": "user", "content": user})
            model = kwargs.get("model", Config.OPENAI_MODEL)
        
        return await self.client.chat.completions.create(
            model=model,
            messages=messages,
            response_model=datamodel,
            temperature=kwargs.get("temperature", 0.0),
            max_tokens=kwargs.get("max_tokens", 2048),
        )