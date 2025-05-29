"""
Translation service for Rock Chatbot.

This module provides translation functionality for the Rock chatbot using Google Translate API.
It uses the googletrans library, which is a free and unlimited Python library that implements Google Translate API.
"""

import time
from typing import Dict, Optional, List
import logging
from googletrans import Translator, LANGUAGES

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize the translator
translator = Translator()

# Language code mapping (ISO 639-1 codes)
LANGUAGE_CODES = {
    'en': 'en',  # English
    'ms': 'ms',  # Malay
    'zh': 'zh-cn',  # Chinese (Simplified)
    'ta': 'ta'   # Tamil
}

# Cache for storing translations to reduce API calls
TRANSLATION_CACHE = {}

# Fallback translations for common phrases (used when API fails)
FALLBACK_TRANSLATIONS = {
    'ms': {  # Malay
        'Hello! Welcome to Rock Supplements. How can I help you today?':
            'Halo! Selamat datang ke Rock Supplements. Bagaimana saya boleh membantu anda hari ini?',
        'Browse Products': 'Lihat Produk',
        'Get Recommendations': 'Dapatkan Cadangan',
        'Check Order Status': 'Semak Status Pesanan',
        'Current Promotions': 'Promosi Semasa',
        'Speak to an Agent': 'Bercakap dengan Ejen',
    },
    'zh': {  # Chinese
        'Hello! Welcome to Rock Supplements. How can I help you today?':
            '你好！欢迎来到Rock营养补充品。今天我能帮到你什么？',
        'Browse Products': '浏览产品',
        'Get Recommendations': '获取推荐',
        'Check Order Status': '查询订单状态',
        'Current Promotions': '当前促销',
        'Speak to an Agent': '与客服人员交谈',
    },
    'ta': {  # Tamil
        'Hello! Welcome to Rock Supplements. How can I help you today?':
            'வணக்கம்! Rock Supplements-க்கு வரவேற்கிறோம். இன்று நான் உங்களுக்கு எப்படி உதவ முடியும்?',
        'Browse Products': 'தயாரிப்புகளை பார்வையிடவும்',
        'Get Recommendations': 'பரிந்துரைகளைப் பெறுங்கள்',
        'Check Order Status': 'ஆர்டர் நிலையை சரிபார்க்கவும்',
        'Current Promotions': 'தற்போதைய விளம்பரங்கள்',
        'Speak to an Agent': 'ஒரு முகவருடன் பேசுங்கள்',
    }
}

class TranslationService:
    """
    Translation service for Rock Chatbot using Google Translate API via googletrans library.

    Features:
    - Free and accurate machine translation
    - Caching to reduce API calls and improve performance
    - Fallback mechanism for API failures
    - Support for multiple languages (Malay, Chinese, Tamil)
    - Batch translation capability
    """

    @staticmethod
    def translate(text: str, target_language: str, source_language: str = 'en') -> str:
        """
        Translate text from source language to target language using Google Translate API.

        Args:
            text: The text to translate
            target_language: The target language code (e.g., 'ms', 'zh', 'ta')
            source_language: The source language code (default: 'en')

        Returns:
            The translated text, or the original text if translation fails
        """
        # If target language is English or same as source, return original text
        if target_language == 'en' or target_language == source_language:
            return text

        # Check if translation is in cache
        cache_key = f"{source_language}:{target_language}:{text}"
        if cache_key in TRANSLATION_CACHE:
            logger.info(f"Cache hit for: {cache_key[:30]}...")
            return TRANSLATION_CACHE[cache_key]

        # Check if we have a fallback translation for common phrases
        if target_language in FALLBACK_TRANSLATIONS and text in FALLBACK_TRANSLATIONS[target_language]:
            logger.info(f"Using fallback translation for: {text[:30]}...")
            return FALLBACK_TRANSLATIONS[target_language][text]

        # Translate using googletrans
        try:
            # Map language codes
            target = LANGUAGE_CODES.get(target_language, target_language)

            # Log the translation attempt
            logger.info(f"Translating with googletrans: {text[:30]}... to {target}")

            # Use googletrans to translate
            result = translator.translate(text, dest=target, src=source_language)
            translated_text = result.text

            # Cache the result
            TRANSLATION_CACHE[cache_key] = translated_text

            return translated_text

        except Exception as e:
            logger.error(f"Translation error: {str(e)}")

            # Try fallback for partial matches
            for key, value in FALLBACK_TRANSLATIONS.get(target_language, {}).items():
                if key in text:
                    text = text.replace(key, value)

            return text  # Return original text if translation fails

    @staticmethod
    def translate_button_options(buttons: List[Dict], target_language: str) -> List[Dict]:
        """
        Translate button options.

        Args:
            buttons: List of button dictionaries with 'text' and 'value' keys
            target_language: The target language code

        Returns:
            List of translated button dictionaries
        """
        if target_language == 'en':
            return buttons

        translated_buttons = []
        for button in buttons:
            translated_text = TranslationService.translate(button['text'], target_language)
            # Keep the original value for button functionality
            translated_buttons.append({
                'text': translated_text,
                'value': button['value']
            })

        return translated_buttons

    @staticmethod
    def batch_translate(texts: List[str], target_language: str, source_language: str = 'en') -> List[str]:
        """
        Translate multiple texts at once to reduce API calls.

        Args:
            texts: List of texts to translate
            target_language: The target language code
            source_language: The source language code (default: 'en')

        Returns:
            List of translated texts
        """
        if target_language == 'en' or target_language == source_language:
            return texts

        # Map language code
        target = LANGUAGE_CODES.get(target_language, target_language)

        results = []
        for text in texts:
            # Check cache first
            cache_key = f"{source_language}:{target_language}:{text}"
            if cache_key in TRANSLATION_CACHE:
                results.append(TRANSLATION_CACHE[cache_key])
                continue

            # Check fallback translations
            if target_language in FALLBACK_TRANSLATIONS and text in FALLBACK_TRANSLATIONS[target_language]:
                results.append(FALLBACK_TRANSLATIONS[target_language][text])
                continue

            try:
                # Use googletrans to translate
                result = translator.translate(text, dest=target, src=source_language)
                translated_text = result.text

                # Cache the result
                TRANSLATION_CACHE[cache_key] = translated_text
                results.append(translated_text)

                # Add a small delay to avoid rate limiting
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Batch translation error: {str(e)}")
                results.append(text)  # Use original text on error

        return results
