import streamlit as st
import streamlit_authenticator as stauth
import streamlit.components.v1 as components
import yaml
from yaml.loader import SafeLoader
import json
import pandas as pd
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
import tempfile
import zipfile
import time
import re
from typing import List, Dict, Set , Tuple
from collections import defaultdict
from io import BytesIO
import logging
from datetime import datetime
import traceback
import matplotlib.ticker as mticker
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import seaborn as sns
import arabic_reshaper
from bidi.algorithm import get_display
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
import plotly.express as px
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.styles import NamedStyle
from openpyxl.utils import get_column_letter
from openpyxl import load_workbook
from openpyxl.styles import Border, Side
import math
from datetime import datetime, timedelta
import base64
from matplotlib import font_manager
import numpy as np
# ============================================================================
# بخش 1: تنظیمات اولیه
# ============================================================================

load_dotenv()

def load_css(file_name):
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"فایل '{file_name}' پیدا نشد.")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app_log.txt', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="AI Financial Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

load_css("style.css")


def load_api_keys_from_env():
    """
    این تابع تلاش می‌کند کلیدها را از متغیرهای محیطی بخواند.
    دو روش را پشتیبانی می‌کند:
    1. یک متغیر به نام GOOGLE_API_KEYS که کلیدها با کاما جدا شده‌اند.
    2. متغیرهای جداگانه مثل API_KEY_1, API_KEY_2 و ...
    """
    keys = []
    
    # روش ۱: خواندن همه کلیدها از یک متغیر رشته‌ای (مناسب برای کپی راحت در گیت‌هاب)
    # مثال مقدار: key1,key2,key3
    all_keys_string = os.getenv("GOOGLE_API_KEYS")
    if all_keys_string:
        # جدا کردن با کاما و حذف فاصله‌های اضافی
        keys = [k.strip() for k in all_keys_string.split(',') if k.strip()]
        
    # روش ۲: اگر روش اول پیدا نشد، دنبال کلیدهای جداگانه بگرد
    if not keys:
        i = 1
        while True:
            key = os.getenv(f"API_KEY_{i}") # مثلا API_KEY_1
            if key:
                keys.append(key)
                i += 1
            else:
                break
    
    return keys

# دریافت کلیدها
loaded_keys = load_api_keys_from_env()

# اگر کلیدی در محیط نبود، یک لیست خالی یا یک پیام خطا برگردان
if loaded_keys:
    DEFAULT_API_KEYS = loaded_keys
else:
    # این قسمت فقط برای جلوگیری از کرش کردن برنامه در حالت بدون کلید است
    DEFAULT_API_KEYS = [] 
    # یا می‌توانید خطا دهید: raise ValueError("هیچ API Key یافت نشد!")

if 'api_keys' not in st.session_state:
    st.session_state.api_keys = DEFAULT_API_KEYS.copy()

# ============================================================================
# بخش 2: احراز هویت
# ============================================================================

with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

hashed_passwords = stauth.Hasher(["elnagh", "abc_fin_cba","123"]).generate()
config['credentials']['usernames']['admin']['password'] = hashed_passwords[0]
config['credentials']['usernames']['fin.analyst']['password'] = hashed_passwords[1]
config['credentials']['usernames']['h.khandani']['password'] = hashed_passwords[2]

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
)

if 'authentication_status' not in st.session_state:
    st.session_state.authentication_status = None

if st.session_state.authentication_status is None:
    name, authentication_status, username = authenticator.login(location='main')
    st.session_state.authentication_status = authentication_status
    st.session_state.name = name
    st.session_state.username = username

if st.session_state.authentication_status == False:
    st.error('نام کاربری یا رمز عبور اشتباه است')
    st.stop()

if st.session_state.authentication_status == None:
    st.warning('لطفاً نام کاربری و رمز عبور خود را وارد کنید')
    st.stop()

# ============================================================================
# بخش 3: سایدبار
# ============================================================================

if st.session_state.authentication_status:
    
    
    with st.sidebar:
        st.header("⚙️ تنظیمات برنامه")
        
        # ----------------------------------------------------------------
        # 🎨 بخش استایل‌های CSS اصلاح شده
        # ----------------------------------------------------------------
        st.markdown("""
        <style>
        /* 1. استایل مشترک و زیبا برای Number Input و Select Box */
        [data-testid="stSidebar"] .stNumberInput > div > div > input,
        [data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
            text-align: center !important;
            font-size: 14px !important;
            font-weight: bold !important;
            background-color: #f0f2f6 !important;
            border: 2px solid #e0e0e0 !important;
            border-radius: 8px !important;
            color: #31333F !important;
            min-height: 45px !important;
            display: flex !important;
            align-items: center !important;
        }

        /* حالت فوکوس برای هر دو */
        [data-testid="stSidebar"] .stNumberInput > div > div > input:focus,
        [data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div:focus-within {
            border-color: #667eea !important;
            box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2) !important;
        }

        /* 2. استایل دکمه‌های + و - در Number Input */
        [data-testid="stSidebar"] .stNumberInput button {
            background-color: #667eea !important;
            color: white !important;
            border: none !important;
            border-radius: 6px !important;
            width: 30px !important; 
            height: 35px !important; 
            font-size: 18px !important;
            font-weight: bold !important;
            margin: 0 3px !important;
        }
        
        [data-testid="stSidebar"] .stNumberInput button:hover {
            background-color: #5568d3 !important;
            transform: scale(1.05);
        }
        
        /* 3. کانتینر اصلی Number Input (سایه و پس‌زمینه سفید) */
        [data-testid="stSidebar"] .stNumberInput > div {
            background-color: white !important;
            border-radius: 10px !important;
            padding: 5px !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08) !important;
        }
        
        /* تنظیم رنگ فلش در SelectBox */
        [data-testid="stSidebar"] [data-testid="stSelectbox"] svg {
            fill: #667eea !important;
        }
        
        /* نکته: استایل باکس دور Radio Button حذف شد تا تمام عرض و ساده نمایش داده شود */
        </style>
        """, unsafe_allow_html=True)
        # ----------------------------------------------------------------

        # st.subheader("🔑 کلیدهای API")
        
        # این قسمت حالا داخل کادر استایل‌دهی شده‌ی stRadio نمایش داده می‌شود
        key_input_method = st.radio(
            "روش ورود کلیدها:",
            ["کلیدهای پیش‌فرض", "کلیدهای سفارشی"],
            label_visibility="collapsed" # اگر می‌خواهید عنوان داخل باکس باشد، این را visible کنید
        )
        
        if key_input_method == "کلیدهای پیش‌فرض":
            st.session_state.api_keys = DEFAULT_API_KEYS.copy()
            st.success(f"✅ {len(st.session_state.api_keys)} کلید لود شد")
        else:
            custom_keys_text = st.text_area(
                "کلیدهای API (جدا کننده enter):",
                height=120,
                placeholder="AIzaSy...\nAIzaSy..."
            )
            if custom_keys_text:
                st.session_state.api_keys = [key.strip() for key in custom_keys_text.split('\n') if key.strip()]
                st.success(f"✅ {len(st.session_state.api_keys)} کلید سفارشی")
            else:
                st.session_state.api_keys = DEFAULT_API_KEYS.copy()

        # ============ MODEL SELECTION SECTION ============
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 12px; border-radius: 10px; text-align: center; margin-bottom: 15px; margin-top: 20px;">
            <p style="color: white; margin: 0; font-size: 14px; font-weight: bold;">
                🤖 انتخاب مدل هوش مصنوعی
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Initialize session state for selected model
        if 'selected_model' not in st.session_state:
            st.session_state.selected_model = "gemini-2.5-pro"  
        
        # Model selection with descriptions
        model_options = { 
            "gemini-3-flash-preview": "🚀 Gemini 3 Flash Preview",
            "gemini-3-pro-preview": "💎 Gemini 3 Pro Preview",
             "gemini-2.5-pro": "🎯 Gemini 2.5 Pro",
            "gemini-2.5-flash": "⚡ Gemini 2.5 Flash"
        }
        
        st.session_state.selected_model = st.selectbox(
            "مدل مورد نظر را انتخاب کنید:", 
            options=list(model_options.keys()),
            format_func=lambda x: model_options[x],
            index=list(model_options.keys()).index(st.session_state.selected_model),
            help="مدل مناسب را بر اساس نیاز خود انتخاب کنید"
        )
        
        # Display model info
        # model_info = {
        #     "gemini-2.5-flash": {"speed": "⚡⚡⚡", "accuracy": "⭐⭐⭐", "cost": "💰"},
        #     "gemini-3-flash-preview": {"speed": "⚡⚡⚡", "accuracy": "⭐⭐⭐⭐", "cost": "💰💰"},
        #     "gemini-3-pro-preview": {"speed": "⚡⚡", "accuracy": "⭐⭐⭐⭐⭐", "cost": "💰💰💰"},
        #     "gemini-2.5-pro": {"speed": "⚡⚡", "accuracy": "⭐⭐⭐⭐⭐", "cost": "💰💰💰"}
        # }
        
        # current_info = model_info[st.session_state.selected_model]
        # st.markdown(f"""
        # <div style="background: #f8f9fa; padding: 10px; border-radius: 8px; 
        #             border-right: 4px solid #667eea; margin-bottom: 15px;">
        #     <p style="margin: 3px 0; font-size: 11px; color: #555; text-align: right;">
        #         <strong>سرعت:</strong> {current_info['speed']} | 
        #         <strong>دقت:</strong> {current_info['accuracy']} | 
        #         <strong>هزینه:</strong> {current_info['cost']}
        #     </p>
        # </div>
        # """, unsafe_allow_html=True)
        
        st.divider()
        # ============ END MODEL SELECTION ============
        # st.markdown('<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 12px; border-radius: 10px; text-align: center; margin-bottom: 15px;"><p style="color: white; margin: 0; font-size: 14px; font-weight: bold;">🎛️ پارامترهای محدودیت API</p></div>', unsafe_allow_html=True)
        # Initialize session state for API limits if not exists
        if 'max_tokens_per_min' not in st.session_state:
            st.session_state.max_tokens_per_min = 125000
        if 'max_requests_per_min' not in st.session_state:
            st.session_state.max_requests_per_min = 2
        if 'max_requests_per_day' not in st.session_state:
            st.session_state.max_requests_per_day = 50
        

        with st.expander("⚡ تنظیمات پیشرفته محدودیت‌های API", expanded=False):   
            # Tokens per minute
            # st.markdown('<div style="background: #e3f2fd; padding: 10px; border-radius: 8px; margin-bottom: 12px; border-right: 4px solid #2196f3;">', unsafe_allow_html=True)
            st.markdown('<p style="margin: 0 0 8px 0; font-size: 12px; font-weight: 600; color: #7b1fa2; text-align: right;">🟣 حداکثر توکن در دقیقه (هر API)</p>', unsafe_allow_html=True)
            st.session_state.max_tokens_per_min = st.number_input(
                "max_tokens_label",
                min_value=1000,
                max_value=1000000,
                value=st.session_state.max_tokens_per_min,
                step=5000,
                label_visibility="collapsed",
                help="تعداد توکن‌های قابل پردازش در هر دقیقه برای هر API Key"
            )
            # st.markdown(f'<p style="margin: 5px 0 0 0; font-size: 11px; color: #666; text-align: center;">مقدار فعلی: <strong>{st.session_state.max_tokens_per_min:,}</strong> توکن</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Requests per minute
            # st.markdown('<div style="background: #fff3e0; padding: 10px; border-radius: 8px; margin-bottom: 12px; border-right: 4px solid #ff9800;">', unsafe_allow_html=True)
            st.markdown('<p style="margin: 0 0 8px 0; font-size: 12px; font-weight: 600; color: #7b1fa2; text-align: right;">🟣 حداکثر درخواست در دقیقه (هر API)</p>', unsafe_allow_html=True)
            st.session_state.max_requests_per_min = st.number_input(
                "max_requests_min_label",
                min_value=1,
                max_value=100,
                value=st.session_state.max_requests_per_min,
                step=1,
                label_visibility="collapsed",
                help="تعداد درخواست‌های مجاز در هر دقیقه برای هر API Key"
            )
            # st.markdown(f'<p style="margin: 5px 0 0 0; font-size: 11px; color: #666; text-align: center;">مقدار فعلی: <strong>{st.session_state.max_requests_per_min}</strong> درخواست</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Requests per day
            # st.markdown('<div style="background: #f3e5f5; padding: 10px; border-radius: 8px; margin-bottom: 12px; border-right: 4px solid #9c27b0;">', unsafe_allow_html=True)
            st.markdown('<p style="margin: 0 0 8px 0; font-size: 12px; font-weight: 600; color: #7b1fa2; text-align: right;">🟣 حداکثر درخواست در روز (هر API)</p>', unsafe_allow_html=True)
            st.session_state.max_requests_per_day = st.number_input(
                "max_requests_day_label",
                min_value=1,
                max_value=10000,
                value=st.session_state.max_requests_per_day,
                step=10,
                label_visibility="collapsed",
                help="تعداد کل درخواست‌های مجاز در هر روز برای هر API Key"
            )
            # st.markdown(f'<p style="margin: 5px 0 0 0; font-size: 11px; color: #666; text-align: center;">مقدار فعلی: <strong>{st.session_state.max_requests_per_day}</strong> درخواست</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        # st.markdown("---")
        st.markdown("""
        <div style="background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%); padding: 12px; border-radius: 8px; border: 1px solid #e0e0e0;">
            <p style="margin: 0; font-size: 12px; color: #424242; text-align: right; line-height: 1.6;">
            💡 <strong>هشدار:</strong> این مقادیر بر اساس محدودیت‌های Gemini API تنظیم شده‌اند. 
            تغییر آن‌ها می‌تواند بر سرعت و دقت پردازش تأثیر بگذارد.
            در صورتی که اطلاع دقیق از محدودیت ها و تغییرات مدل ندارید تنظیمات را تغییر ندهید.
             </p>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        

        
        #########
       
        
       


        st.info('''
        ⚙️ **پردازش هوشمند**

        پردازش فایل‌ها بصورت همزمان و موازی انجام خوهد شد
        
        تعداد فایل‌های همزمان به صورت خودکار 
        بر اساس موارد زیر محاسبه می‌شود:

        ✅  تعداد API Keys  
        ✅ محدودیت‌های مدل  
        ✅ تعداد فایل‌ها  
        ✅ حافظه سیستم
        ''')

        st.markdown("<div style='margin-top: auto;'></div>", unsafe_allow_html=True)
        authenticator.logout('🚪 خروج از سیستم', 'sidebar')


    class APILimitsManager:
        """مدیریت هوشمند محدودیت‌های API و محاسبه تعداد workers بهینه"""
        
        # # محدودیت‌های Gemini API
        # MAX_TOKENS_PER_MIN = 125_000      # tokens per minute per API
        # MAX_REQUESTS_PER_MIN = 2          # Maximum requests per minute per API
        # MAX_REQUESTS_PER_DAY = 50         # Maximum requests per day per API
        
        # تخمین‌ها برای هر فایل PDF
        AVG_TOKENS_PER_FILE = 20_000      # تخمین متوسط tokens برای هر فایل
        AVG_PROCESSING_TIME = 30          # تخمین زمان پردازش هر فایل (ثانیه)
        
        def __init__(self, api_keys: list , max_tokens_per_min: int, max_requests_per_min: int, max_requests_per_day: int):
            """
            Args:
                api_keys: لیست API keys موجود
            """
            self.num_api_keys = len(api_keys)
            self.api_usage = {key: {'requests_today': 0, 'last_reset': datetime.now()} 
                            for key in api_keys}

             # ✅ مقادیر محدودیت‌ها اکنون از ورودی‌های تابع init گرفته می‌شوند
            self.MAX_TOKENS_PER_MIN = max_tokens_per_min
            self.MAX_REQUESTS_PER_MIN = max_requests_per_min
            self.MAX_REQUESTS_PER_DAY = max_requests_per_day      


        def calculate_optimal_workers(self, num_files: int, file_sizes: list = None) -> dict:
            """
            محاسبه تعداد بهینه workers بر اساس محدودیت‌های API
            
            Args:
                num_files: تعداد فایل‌های ورودی
                file_sizes: اندازه فایل‌ها (اختیاری) برای تخمین دقیق‌تر
            
            Returns:
                dict: شامل تعداد workers، زمان تخمینی، و توضیحات
            """
            
            # 1️⃣ محاسبه بر اساس محدودیت Requests Per Minute
            # هر API می‌تواند 2 request در دقیقه داشته باشد
            max_workers_rpm = self.num_api_keys * self.MAX_REQUESTS_PER_MIN
            
            # 2️⃣ محاسبه بر اساس محدودیت Tokens Per Minute
            # با فرض هر فایل 20K token
            max_files_per_min_tokens = (self.num_api_keys * self.MAX_TOKENS_PER_MIN) / self.AVG_TOKENS_PER_FILE
            max_workers_tokens = math.floor(max_files_per_min_tokens)
            
            # 3️⃣ محاسبه بر اساس محدودیت Daily Requests
            # هر API: 50 request در روز
            max_daily_files = self.num_api_keys * self.MAX_REQUESTS_PER_DAY
            
            # 4️⃣ محدودیت عملی: زمان پردازش
            # اگر هر فایل 30 ثانیه طول بکشد و ما 60 ثانیه داریم
            # می‌توانیم حداکثر 2 بار از هر API استفاده کنیم (مطابق با RPM)
            processing_based_workers = max_workers_rpm
            
            # 5️⃣ انتخاب کمترین مقدار (bottleneck)
            optimal_workers = min(
                max_workers_rpm,          # محدودیت RPM
                max_workers_tokens,       # محدودیت tokens
                num_files,                # تعداد فایل‌ها
                10                        # حداکثر منطقی برای جلوگیری از اشغال منابع
            )
            
            # اطمینان از اینکه حداقل 1 worker داریم
            optimal_workers = max(1, optimal_workers)
            
            # 6️⃣ محاسبه زمان تخمینی
            # با پردازش موازی
            estimated_time_parallel = (num_files / optimal_workers) * self.AVG_PROCESSING_TIME
            # بدون پردازش موازی
            estimated_time_sequential = num_files * self.AVG_PROCESSING_TIME
            
            # 7️⃣ بررسی محدودیت روزانه
            daily_limit_ok = num_files <= max_daily_files
            
            # 8️⃣ تعیین استراتژی
            if num_files <= max_workers_rpm:
                strategy = "fast_parallel"
                message = f"✅ پردازش سریع: همه فایل‌ها به طور همزمان ({optimal_workers} worker)"
            elif num_files <= max_daily_files:
                strategy = "batch_parallel"
                message = f"⚡ پردازش دسته‌ای: {optimal_workers} worker با چند batch"
            else:
                strategy = "limited"
                optimal_workers = min(optimal_workers, 3)
                message = f"⚠️ محدودیت روزانه: فقط {max_daily_files} فایل امکان‌پذیر است"
            
            return {
                'optimal_workers': optimal_workers,
                'strategy': strategy,
                'message': message,
                'estimated_time_minutes': estimated_time_parallel / 60,
                'speedup_factor': estimated_time_sequential / estimated_time_parallel,
                'limits': {
                    'max_rpm': max_workers_rpm,
                    'max_tokens': max_workers_tokens,
                    'max_daily': max_daily_files,
                    'files_count': num_files,
                    'daily_limit_ok': daily_limit_ok
                },
                'explanation': self._generate_explanation(
                    optimal_workers, 
                    num_files, 
                    max_workers_rpm,
                    estimated_time_parallel
                )
            }
        
        def _generate_explanation(self, workers: int, files: int, max_rpm: int, time_min: float) -> str:
            """تولید توضیحات برای کاربر"""
            explanations = []
            
            explanations.append(f"🔧 **تنظیمات محاسبه شده:**")
            explanations.append(f"  • تعداد API Keys: {self.num_api_keys}")
            explanations.append(f"  • تعداد فایل‌ها: {files}")
            explanations.append(f"  • Workers بهینه: {workers}")
            explanations.append(f"  • زمان تخمینی: {time_min:.1f} دقیقه")
            
            explanations.append(f"\n📊 **محدودیت‌های API:**")
            explanations.append(f"  • حداکثر همزمان: {max_rpm} فایل در دقیقه")
            explanations.append(f"  • هر API: {self.MAX_REQUESTS_PER_MIN} request/min")
            explanations.append(f"  • محدودیت روزانه: {self.MAX_REQUESTS_PER_DAY * self.num_api_keys} فایل")
            
            if files > max_rpm:
                batches = math.ceil(files / workers)
                explanations.append(f"\n⚡ **استراتژی پردازش:**")
                explanations.append(f"  • پردازش در {batches} دسته")
                explanations.append(f"  • هر دسته: {workers} فایل همزمان")
            
            return "\n".join(explanations)

    
    # ============================================================================
    # 🔄 تابع اصلاح شده: پردازش با محاسبه خودکار workers
    # ============================================================================

    def process_files_concurrent_smart(uploaded_files):
        """
        ✅ پردازش همزمان با محاسبه خودکار تعداد workers بهینه
        
        ویژگی‌های جدید:
        - محاسبه خودکار workers بر اساس محدودیت‌های API
        - نمایش توضیحات کامل برای کاربر
        - بهینه‌سازی منابع
        """
        try:
            selected_model = st.session_state.get('selected_model', 'gemini-2.5-pro')
            logger.info(f"📌 Selected model for processing: {selected_model}")
        except Exception as e:
            selected_model = 'gemini-2.5-pro'
            logger.warning(f"⚠️ Could not access session_state ({str(e)}), using default model: {selected_model}")
        
        # 2️⃣ محاسبه تعداد workers بهینه
        limits_manager = APILimitsManager(   
            api_keys=st.session_state.api_keys,
            max_tokens_per_min=st.session_state.max_tokens_per_min,
            max_requests_per_min=st.session_state.max_requests_per_min,
            max_requests_per_day=st.session_state.max_requests_per_day
        )

        optimization = limits_manager.calculate_optimal_workers(
            num_files=len(uploaded_files)
        )
        
        optimal_workers = optimization['optimal_workers']
        
        # 2️⃣ نمایش اطلاعات برای کاربر
        st.markdown('<div class="modern-card">', unsafe_allow_html=True)
  
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 3️⃣ بررسی محدودیت روزانه
        if not optimization['limits']['daily_limit_ok']:
            st.error(
                f"⚠️ تعداد فایل‌ها ({len(uploaded_files)}) بیشتر از محدودیت روزانه "
                f"({optimization['limits']['max_daily']}) است. "
                f"لطفاً تعداد فایل‌ها را کاهش دهید یا API key های بیشتری اضافه کنید."
            )
            return None
        
        # 4️⃣ شروع پردازش با workers محاسبه شده
        analyzer = FinancialAnalyzer()
        total_files = len(uploaded_files)
        max_retry_attempts = 3
        
        st.markdown('<div class="modern-card"><h3>در حال پردازش...</h3></div>', unsafe_allow_html=True)
        progress_bar = st.progress(0)
        status_placeholder = st.empty()
        status_container = st.container()
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        metric_success = col1.empty()
        metric_failed = col2.empty()
        metric_retrying = col3.empty()
        metric_total = col4.empty()
        
        results = [None] * total_files
        completed = 0
        failed_count = 0
        retry_count = 0
        start_time = time.time()
        files_to_retry = []
        
        # 5️⃣ پردازش اولیه با optimal_workers
        with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            future_to_index = {
                executor.submit(process_single_file, analyzer, file, i, total_files, 1, max_retry_attempts, selected_model ): i
                for i, file in enumerate(uploaded_files)
            }
            
            for future in as_completed(future_to_index):
                index, filename, result, error, needs_retry = future.result()
                completed += 1
                
                if error:
                    if needs_retry:
                        files_to_retry.append((index, uploaded_files[index], filename, 2))
                        retry_count += 1
                        with status_container:
                            st.warning(f'🔄 **{filename}** نیاز به تلاش مجدد دارد ({completed}/{total_files})')
                    else:
                        results[index] = (filename, {"error": f"خطا: {error}"})
                        failed_count += 1
                        with status_container:
                            st.error(f'❌ **{filename}**: خطای غیرقابل بازیابی')
                else:
                    results[index] = (filename, result)
                    with status_container:
                        st.success(f'✅ **{filename}** ({completed}/{total_files})')
                
                progress_bar.progress(completed / total_files)
                
                metric_success.metric("✅ موفق", len([r for r in results if r and 'error' not in r[1]]))
                metric_failed.metric("❌ ناموفق", failed_count)
                metric_retrying.metric("🔄 در انتظار تلاش مجدد", len(files_to_retry))
                metric_total.metric("📊 کل", total_files)
                
                elapsed = time.time() - start_time
                avg_time = elapsed / completed
                remaining = (total_files - completed + len(files_to_retry)) * avg_time
                status_placeholder.info(
                    f'📊 پردازش اولیه: {completed}/{total_files} | '
                    f'⏱️ زمان: {elapsed:.1f}s | ⏳ تخمین: {remaining:.1f}s | '
                    f'🤖 مدل: {selected_model}'  # 👈 نمایش مدل در حال استفاده
                )
        
        # 6️⃣ مرحله Retry (اگر نیاز باشد)
        if files_to_retry:
            st.markdown("---")
            st.markdown(f"### 🔄 تلاش مجدد برای فایل‌های ناموفق با مدل {selected_model}...")
            
            retry_attempt = 1
            # در retry از نصف workers استفاده می‌کنیم
            retry_workers = max(1, optimal_workers // 2)
            
            while files_to_retry and retry_attempt <= max_retry_attempts:
                st.info(f"🔄 دور {retry_attempt} از تلاش مجدد ({len(files_to_retry)} فایل) با {retry_workers} worker")
                
                delay = min(5 * retry_attempt, 15)
                with st.spinner(f'⏳ صبر {delay} ثانیه قبل از تلاش مجدد...'):
                    time.sleep(delay)
                
                current_retry_list = files_to_retry.copy()
                files_to_retry = []
                
                with ThreadPoolExecutor(max_workers=retry_workers) as executor:
                    future_to_data = {
                        executor.submit(
                            process_single_file, 
                            analyzer, 
                            file_data, 
                            idx, 
                            total_files, 
                            attempt_num,
                            max_retry_attempts,
                            selected_model  
                        ): (idx, fname, attempt_num)
                        for idx, file_data, fname, attempt_num in current_retry_list
                    }
                    
                    for future in as_completed(future_to_data):
                        idx, fname, attempt_num = future_to_data[future]
                        index, filename, result, error, needs_retry = future.result()
                        
                        if error:
                            if needs_retry and attempt_num < max_retry_attempts:
                                files_to_retry.append((index, uploaded_files[index], filename, attempt_num + 1))
                                with status_container:
                                    st.warning(f'🔄 **{filename}** - تلاش {attempt_num + 1}/{max_retry_attempts}')
                            else:
                                results[index] = (filename, {"error": f"خطا بعد از {attempt_num} تلاش: {error}"})
                                failed_count += 1
                                with status_container:
                                    st.error(f'❌ **{filename}**: ناموفق بعد از {attempt_num} تلاش')
                        else:
                            results[index] = (filename, result)
                            with status_container:
                                st.success(f'✅ **{filename}** موفق در تلاش {attempt_num}!')
                            failed_count = max(0, failed_count - 1)
                        
                        successful = len([r for r in results if r and 'error' not in r[1]])
                        metric_success.metric("✅ موفق", successful)
                        metric_failed.metric("❌ ناموفق", failed_count)
                        metric_retrying.metric("🔄 در انتظار تلاش مجدد", len(files_to_retry))
                
                retry_attempt += 1
        
        # 7️⃣ گزارش نهایی
        total_duration = time.time() - start_time
        successful = len([r for r in results if r and 'error' not in r[1]])
        
        st.markdown("---")
        
        if failed_count == 0:
            status_placeholder.success(
                f'🎉 همه فایل‌ها با موفقیت پردازش شدند! '
                f'{total_files} فایل در {total_duration:.1f} ثانیه ({total_duration/60:.1f} دقیقه)'
                f'با مدل {selected_model}'
            )
        else:
            status_placeholder.warning(
                f'⚠️ پردازش تکمیل شد: {successful}/{total_files} موفق، {failed_count} ناموفق '
                f'در {total_duration:.1f} ثانیه ({total_duration/60:.1f} دقیقه)'
                f'با مدل {selected_model}'
            )
        
        if retry_count > 0:
            st.info(f'ℹ️ تعداد فایل‌هایی که نیاز به تلاش مجدد داشتند: {retry_count}')
        
        # نمایش مقایسه با زمان تخمینی
        estimated_time = optimization['estimated_time_minutes'] * 60
        if abs(total_duration - estimated_time) < estimated_time * 0.2:  # ±20%
            st.success(f"✅ زمان پردازش مطابق تخمین بود!")
        elif total_duration < estimated_time:
            st.success(f"🚀 پردازش {(estimated_time - total_duration):.0f} ثانیه سریع‌تر از تخمین بود!")
        
        return results
    


    # ========================================================================
    # بخش 4: کلاس‌ها و توابع اصلی (بدون تغییر)
    # ========================================================================

    class APIKeyManager:
        def __init__(self, api_keys: List[str]):
            if not api_keys:
                raise ValueError("API keys list cannot be empty.")
            self.api_keys = api_keys
            self.current_index = 0
            self.failures = {key: 0 for key in api_keys}
            self.max_failures = 3
            self.lock = threading.Lock()  # ✅ اضافه شده برای thread-safety
            
        def get_next_key(self) -> str:
            with self.lock:  # ✅ محافظت از race condition
                attempts = 0
                while attempts < len(self.api_keys):
                    key = self.api_keys[self.current_index]
                    self.current_index = (self.current_index + 1) % len(self.api_keys)
                    if self.failures.get(key, 0) < self.max_failures:
                        return key
                    attempts += 1
                logger.warning("All API keys have failed, resetting failure counters")
                self.failures = {key: 0 for key in self.api_keys}
                return self.api_keys[0]
        
        def mark_failure(self, key: str):
            with self.lock:
                if key in self.failures:
                    self.failures[key] += 1
                    logger.warning(f"API key failure count for {key[:8]}...: {self.failures[key]}")
        
        def mark_success(self, key: str):
            with self.lock:
                if key in self.failures:
                    self.failures[key] = 0

    api_key_manager = APIKeyManager(st.session_state.api_keys)

    def get_client_with_retry():
        api_key = api_key_manager.get_next_key()
        return genai.Client(api_key=api_key, http_options={"base_url": "https://api.avalai.ir"}), api_key

    # ========================================================================
    # بخش 5: توابع پردازش فارسی و ادغام
    # ========================================================================

# این کد را به طور کامل جایگزین تابع setup_persian_font فعلی خود کنید

    def setup_persian_font():
        """
        تنظیم فونت Vazirmatn برای Matplotlib با استفاده از FontManager
        """
        try:
            
            
            # ✅ مسیر فایل فونت
            font_path = 'fonts/NotoNaskhArabic-Regular.ttf'
            
            if os.path.exists(font_path):
                # ✅ اضافه کردن فونت به Font Manager
                font_manager.fontManager.addfont(font_path)
                
                # ✅ تنظیم به عنوان فونت پیش‌فرض
                plt.rcParams['font.family'] = 'Noto Naskh Arabic'
                plt.rcParams['axes.unicode_minus'] = False
                
                logger.info("✅ فونت Noto Naskh Arabic با موفقیت لود شد")
                
                # برگرداندن FontProperties برای استفاده مستقیم
                return FontProperties(fname=font_path)
                
            else:
                logger.warning(f"⚠️ فایل فونت پیدا نشد: {font_path}")
                # Fallback به Tahoma
                plt.rcParams['font.family'] = ['Tahoma', 'Arial', 'DejaVu Sans']
                plt.rcParams['axes.unicode_minus'] = False
                return FontProperties(family='Tahoma')
                
        except Exception as e:
            logger.error(f"❌ خطا در تنظیم فونت: {e}")
            plt.rcParams['font.family'] = ['Tahoma', 'Arial']
            plt.rcParams['axes.unicode_minus'] = False
            return FontProperties()

    def process_persian_text(text):
        reshaped_text = arabic_reshaper.reshape(str(text))
        bidi_text = get_display(reshaped_text)
        return bidi_text

    def merge_excel_files(excel_files):
        if len(excel_files) < 2:
            return None
        
        merged_data = {}
        company_names = []
        
        try:
            for file_path in excel_files:
                df_summary = pd.read_excel(file_path, sheet_name="بخش1_خلاصه")
                if not df_summary.empty and 'نام_شرکت' in df_summary.columns:
                    company_names.append(df_summary['نام_شرکت'].iloc[0])
            
            if len(set(company_names)) > 1:
                logger.warning("شرکت‌ها هم‌نام نیستند")
                return None
            
            sheet_names = ["بخش1_خلاصه", "بند_تاکید_بر_مطالب_خاص", "بخش3_چک_لیست", "گزارش_قانونی"]
            
            for sheet in sheet_names:
                dfs = []
                for file_path in excel_files:
                    try:
                        df = pd.read_excel(file_path, sheet_name=sheet)
                        dfs.append(df)
                    except:
                        continue
                if dfs:
                    merged_data[sheet] = pd.concat(dfs, ignore_index=True)
            
            return merged_data if merged_data else None
        except Exception as e:
            logger.error(f"خطا در ادغام: {e}")
            return None

    # ========================================================================
    # بخش 6: توابع رسم نمودار (7 نمودار)
    # ========================================================================

    def plot_opinion_trend(df, font):
        """نمودار خطی روند اظهارنظر - با استفاده از میانه (Median) برای تجمیع صحیح"""
        opinion_mp = {'مقبول': 0, 'مشروط': 1, 'مردود': 2, 'عدم اظهارنظر': 3}
        
        df = df.copy()
        df['year'] = pd.to_numeric(df['year'], errors='coerce').astype('Int64')
        df = df.dropna(subset=['year'])
        df["opinion_mp"] = df['نوع_اظهارنظر'].map(opinion_mp)
        df = df.sort_values('year')
        
        # --- اصلاح منطق تجمیع ---
        # به جای میانگین، از میانه (Median) استفاده می‌کنیم و آن را گرد می‌کنیم
        # تا خروجی حتما یکی از اعداد صحیح 0، 1، 2 یا 3 باشد.
        df_grouped = df.groupby('year')['opinion_mp'].median().round().astype(int).reset_index()
        
        fig, ax = plt.subplots(figsize=(12, 7), facecolor='#f8f9fa')
        ax.set_facecolor('#ffffff')

        # 1. رسم نقاط پراکنده (Scatter) در پس‌زمینه
        # این نقاط نشان می‌دهند که در هر سال چه داده‌های دیگری هم وجود داشته است (بدون اتصال خطی)
        # jitter (لرزش) جزئی اضافه می‌کنیم تا نقاط روی هم نیفتند
        jitter_y = df['opinion_mp'] + np.random.uniform(-0.1, 0.1, size=len(df))
        ax.scatter(df['year'], jitter_y, color='#3498db', alpha=0.15, s=50, zorder=1)

        # 2. رسم خط روند اصلی (بر اساس میانه)
        ax.plot(df_grouped['year'], df_grouped['opinion_mp'], 
                marker='o', markersize=12, linestyle='-', 
                linewidth=3, color='#2980b9', zorder=2, label='روند کلی (میانه)')
        
        # تنظیمات ظاهری
        ax.set_xlabel(process_persian_text('سال مالی'), fontproperties=font, size=20, weight='bold', color='#34495e')
        ax.set_ylabel(process_persian_text('نوع اظهار نظر'), fontproperties=font, size=20, weight='bold', color='#34495e')
        
        ax.set_yticks(list(opinion_mp.values()))
        y_labels = [process_persian_text(label) for label in opinion_mp.keys()]
        ax.set_yticklabels(y_labels, fontproperties=font, fontsize=20)
        
        if len(df_grouped) > 0:
            years = sorted(df_grouped['year'].unique())
            ax.set_xticks(years)
            ax.set_xticklabels([int(y) for y in years], fontproperties=font, fontsize=20)
        
        ax.set_ylim(-0.5, 3.5)
        ax.grid(True, linestyle='--', alpha=0.3, color='#bdc3c7')
        
        # حذف حاشیه‌های اضافی
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#bdc3c7')
        ax.spines['bottom'].set_color('#bdc3c7')
        
        if ax.get_legend():
            ax.get_legend().remove()
                
        return fig


    def plot_risk_trend(df, font):
        """نمودار خطی روند سطح ریسک - با استفاده از میانه (Median)"""
        risk_level = ['پایین', 'متوسط', 'بالا', 'بحرانی']
        risk_mp = {'پایین': 0, 'متوسط': 1, 'بالا': 2, 'بحرانی': 3}
        
        df = df.copy()
        df['year'] = pd.to_numeric(df['year'], errors='coerce').astype('Int64')
        df = df.dropna(subset=['year'])
        df["risk_mp"] = df['سطح_ریسک_کلی_بنا_به_گزارش'].map(risk_mp)
        df = df.sort_values('year')
        
        # --- اصلاح منطق تجمیع ---
        # استفاده از میانه و گرد کردن به نزدیکترین عدد صحیح
        df_grouped = df.groupby('year')['risk_mp'].median().round().astype(int).reset_index()

        fig, ax = plt.subplots(figsize=(12, 7), facecolor='#f8f9fa')
        ax.set_facecolor('#ffffff')
        
        # 1. رسم تمام داده‌ها به صورت کم‌رنگ (برای نمایش توزیع)
        jitter_y = df['risk_mp'] + np.random.uniform(-0.1, 0.1, size=len(df))
        ax.scatter(df['year'], jitter_y, color='#e74c3c', alpha=0.15, s=50, zorder=1)

        # 2. رسم خط روند اصلی (میانه)
        ax.plot(df_grouped['year'], df_grouped['risk_mp'], 
                marker='o', markersize=12, linestyle='-', 
                linewidth=3, color='#c0392b', zorder=2)
        
        ax.set_xlabel(process_persian_text('سال مالی'), fontproperties=font, size=20, weight='bold', color='#34495e')
        ax.set_ylabel(process_persian_text('سطح ریسک'), fontproperties=font, size=20, weight='bold', color='#34495e')

        ax.set_yticks(list(risk_mp.values()))
        y_labels = [process_persian_text(label) for label in risk_mp.keys()]
        ax.set_yticklabels(y_labels, fontproperties=font, fontsize=20)
        
        if len(df_grouped) > 0:
            years = sorted(df_grouped['year'].unique())
            ax.set_xticks(years)
            ax.set_xticklabels([int(y) for y in years], fontproperties=font, fontsize=20)
        
        ax.set_ylim(-0.5, len(risk_level) - 0.5)
        ax.grid(True, linestyle='--', alpha=0.3, color='#bdc3c7')
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#bdc3c7')
        ax.spines['bottom'].set_color('#bdc3c7')
        
        if ax.get_legend():
            ax.get_legend().remove()
            
        return fig

    def plot_checklist_heatmap(df, font):
        """نقشه حرارتی - سایز بزرگتر"""
        status_mapping = {
            'مصداق ندارد': 0,
            'بررسی شده - ریسک خاصی گزارش نشده': 1,
            'مسئله کلیدی منجر به اظهارنظر مشروط': 2,
            'ریسک بحرانی': 3
        }
        
        df["status_mp"] = df['وضعیت'].map(status_mapping)
        # irrelevant_topics = [
        #     'آخرین صفحه گزارش حسابرس و بازرس که شامل امضا سازمان حسابرس میشود',
        #     'صفحه امضا های سازمان حسابرسی'
        # ]
        # df = df[~df['موضوع'].isin(irrelevant_topics)]

        heatmap_index =[
                        "کفایت سرمایه",
                        "نسبت‌ها در چارچوب بازل",
                        "ریسک نقدینگی",
                        "مدیریت دارایی و بدهی (ALM)",
                        "ریسک نرخ بهره",
                        "تمرکز ریسک اعتباری",
                        "ذخیره‌گیری (کلی)",
                        "صورت جریان وجوه نقد",
                        "کنترل‌های داخلی و حسابرسی داخلی",
                        "حاکمیت شرکتی",
                        "اوراق بهادار و سرمایه‌گذاری‌ها",
                        "تسعیر ارز و عملیات خارجی",
                        "تعهدات ارزی و اختلاف با بانک مرکزی",
                        "ذخیره مطالبات مشکوک‌الوصول",
                        "مطالبات مشکوک‌الوصول",
                        "تسهیلات و اعتبارات",
                        "سرمایه‌گذاری در شرکت‌های وابسته",
                        "کاهش ارزش دارایی‌ها",
                        "افشای ریسک‌های عملیاتی",
                        "نسبت‌های بدهی و نقدینگی",
                        "نسبت کفایت سرمایه",
                        "معاملات با اشخاص وابسته",
                        "تداوم فعالیت",
                        "انطباق با مقررات ضدپولشویی (AML/CFT)"
]

        heatmap_data = df.pivot_table(index='موضوع', columns='year', values='status_mp', aggfunc='max').fillna(0).astype(int)
    # این کار ترتیب را حفظ می‌کند و موضوعات ناموجود را حذف می‌کند
        filtered_index = [topic for topic in heatmap_index if topic in heatmap_data.index]

        # Reindex با لیست فیلتر شده برای اطمینان از ترتیب صحیح
        heatmap_data = heatmap_data.reindex(filtered_index)

        custom_colors = ["#E0E7FF", "#8EA4E9", "#A970DE", "#F46E52"]
        custom_cmap = LinearSegmentedColormap.from_list("modern_risk", custom_colors, N=4)
        norm = BoundaryNorm(boundaries=[-0.5, 0.5, 1.5, 2.5, 3.5], ncolors=4)
        
        # ✅ سایز بزرگ برای heatmap: 16x10
        fig, ax = plt.subplots(figsize=(12, 7.5), facecolor='#f8f9fa')
        
        sns.heatmap(
            heatmap_data, annot=False, cmap=custom_cmap, norm=norm,
            linewidths=2.5, linecolor='white', fmt='d', cbar=True, ax=ax,
            annot_kws={'fontsize': 11, 'weight': 'bold'},
            cbar_kws={'shrink': 0.8}
        )
        
        # ax.set_title(process_persian_text('نقشه حرارتی ریسک‌های کلیدی در طول زمان'),
        #             fontproperties=font, size=20, weight='bold', pad=25, color='#2c3e50')
        ax.set_xlabel(process_persian_text('سال مالی'), fontproperties=font, size=14, weight='bold', color='#34495e')
        ax.set_ylabel(process_persian_text('موضوعات کلیدی'), fontproperties=font, size=14, weight='bold', color='#34495e')
        
        y_labels = [process_persian_text(label) for label in heatmap_data.index]
        x_labels = [process_persian_text(str(int(label))) for label in heatmap_data.columns]
        ax.set_yticklabels(y_labels, fontproperties=font, rotation=0, fontsize=11)
        ax.set_xticklabels(x_labels, fontproperties=font, rotation=0, fontsize=12)
        
        cbar = ax.collections[0].colorbar
        cbar.set_ticks(list(status_mapping.values()))
        cbar_labels = [process_persian_text(label) for label in status_mapping.keys()]
        cbar.set_ticklabels(cbar_labels, fontproperties=font, fontsize=11)
        cbar.ax.set_title(process_persian_text('سطح ریسک'), fontproperties=font, fontsize=13, pad=15)
        cbar.outline.set_linewidth(2)
        cbar.outline.set_edgecolor('#bdc3c7')
        
        # for spine in ax.spines.values():
        #     spine.set_visible(False)
        
        plt.tight_layout()
        return fig
    

    def plot_risk_stacked_bar(df, font):
        """نمودار ستونی انباشته ریسک‌ها - فقط موارد دارای موضوعیت"""
        

        df = df[df.get('موضوعیت_دارد', True) == True].copy()
        
        if df.empty:
            # اگر داده‌ای نبود، یک figure خالی برگردان
            fig, ax = plt.subplots(figsize=(12, 10), facecolor='#f8f9fa')
            ax.text(0.5, 0.5, process_persian_text('داده‌ای برای نمایش وجود ندارد'), 
                    ha='center', va='center', fontsize=16, fontproperties=font)
            ax.axis('off')
            return fig
        
        risk_over_time = pd.crosstab(df['year'], df['دسته_اصلی_ریسک'])
        
        fig, ax = plt.subplots(figsize=(12, 10), facecolor='#f8f9fa')
        ax.set_facecolor('#ffffff')
        
        colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22']
        risk_over_time.plot(kind='bar', stacked=True, color=colors, ax=ax, width=0.8, edgecolor='white', linewidth=2)
        
        for c in ax.containers:
            labels = [int(v.get_height()) if v.get_height() > 0 else '' for v in c]
            ax.bar_label(c, labels=[f'{v}' if v else '' for v in labels], 
                        label_type='center', color='white', weight='bold', fontsize=20, fontproperties=font)
        
        # ax.set_title(process_persian_text('روند تعداد و ترکیب ریسک‌ها در طول زمان'), 
        #             fontproperties=font, size=18, weight='bold', pad=20, color='#2c3e50')
        ax.set_xlabel(process_persian_text('سال مالی'), fontproperties=font, size=20, weight='bold', color='#34495e')
        ax.set_ylabel(process_persian_text('تعداد ریسک‌های برجسته شده'), fontproperties=font, size=25, weight='bold', color='#34495e')
        ax.tick_params(axis='x', rotation=0, labelsize=20)
        ax.tick_params(axis='y', labelsize=20)
        
        ax.grid(True, axis='y', linestyle='--', alpha=0.3, color='#bdc3c7')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#bdc3c7')
        ax.spines['bottom'].set_color('#bdc3c7')
        
        legend = ax.get_legend()
        # legend.set_title(process_persian_text('دسته اصلی ریسک'), prop=font)
        title_font = font.copy()
        title_font.set_size(17) 
        legend.set_title(process_persian_text('دسته اصلی ریسک'), prop=title_font)
        legend.set_frame_on(True)
        legend.get_frame().set_facecolor('#ffffff')
        legend.get_frame().set_edgecolor('#bdc3c7')
        legend.get_frame().set_linewidth(1.5)
        for text in legend.get_texts():
            text.set_text(process_persian_text(text.get_text()))
            text.set_fontproperties(font)
            text.set_fontsize(17)
        # 6. جابجایی legend به بیرون از نمودار
        # bbox_to_anchor=(1.02, 1) به معنی:
        # 1.02: کمی به سمت راست بیرون از محور x نمودار (102%)
        # 1: در بالای محور y نمودار (100%)
        # loc='upper left' به matplotlib می‌گوید که نقطه بالا-چپ کادر legend را در آن مختصات قرار بده.
#         legend.set_bbox_to_anchor((1.02, 1))
# rect=[0, 0, 0.85, 1]
        # plt.tight_layout()
        plt.subplots_adjust(right=0.82)
        return fig


    def plot_risk_sunburst(df):
        """📊 نمودار Sunburst ریسک‌ها - نسخه نهایی با طراحی مشابه تخلفات و مرکز با عنوان 'ریسک‌های برجسته'"""

        sunburst_data = df.groupby(['دسته_اصلی_ریسک', 'زیرشاخه_ریسک']).size().reset_index(name='تعداد')

        fig = px.sunburst(
            sunburst_data,
            path=[px.Constant("ریسک‌های برجسته"), 'دسته_اصلی_ریسک', 'زیرشاخه_ریسک'],
            values='تعداد',
            color='دسته_اصلی_ریسک',
            color_discrete_sequence=px.colors.qualitative.Set3,
            hover_data={'تعداد': True}
        )

        fig.update_layout(
            width=900,
            height=700,
            # title={
            #     'text': 'تحلیل سلسله‌مراتبی توزیع ریسک‌ها',
            #     'y': 0.98,
            #     'x': 0.5,
            #     'xanchor': 'center',
            #     'yanchor': 'top',
            #     'font': {'size': 22, 'family': 'Tahoma', 'color': '#2c3e50'}
            # },
            font_family="Noto Naskh Arabic",
            font_size=13,
            margin=dict(t=80, l=40, r=40, b=40),
            paper_bgcolor='#f8f9fa',
            plot_bgcolor='#ffffff',
            hovermode='closest',
            hoverlabel=dict(
                bgcolor="white",
                font_size=20,
                font_family="Noto Naskh Arabic",
                align="right"
            ),
            # ✅ افزودن متن مرکز

        )

        # تنظیمات ترسیم جزئیات نمودار
        fig.update_traces(
            textinfo="label",
            insidetextorientation='horizontal',  # افقی برای خوانایی بهتر
            marker=dict(
                line=dict(color='white', width=2.5)
            ),
            textfont=dict(
                size=20,
                family="Noto Naskh Arabic",
                color="black"
            ),
            hovertemplate='<b style="font-family:Noto Naskh Arabic">%{label}</b><br>' +
                        '<span style="font-family:Noto Naskh Arabic">تعداد: %{value}</span><br>' +
                        '<span style="font-family:Noto Naskh Arabic">نسبت: %{percentRoot:.1%}</span>' +
                        '<extra></extra>',
            hoverlabel=dict(
                bgcolor="rgba(255,255,255,0.95)",
                bordercolor="#2c3e50",
                font=dict(family="Noto Naskh Arabic", size=13, color="black")
            )
        )

        return fig



    def plot_violations_stacked_bar(df, font):
        """نمودار ستونی انباشته تخلفات - فقط موارد دارای موضوعیت"""
        
        # ✅ فیلتر کردن فقط موارد دارای موضوعیت
        df = df[df.get('موضوعیت_دارد', True) == True].copy()
        
        if df.empty:
            # اگر داده‌ای نبود، یک figure خالی برگردان
            fig, ax = plt.subplots(figsize=(12,10), facecolor='#f8f9fa')
            ax.text(0.5, 0.5, process_persian_text('داده‌ای برای نمایش وجود ندارد'), 
                    ha='center', va='center', fontsize=16, fontproperties=font)
            ax.axis('off')
            return fig
        
        violation_counts = pd.crosstab(df['year'], df['دسته_اصلی'])
        
        fig, ax = plt.subplots(figsize=(12,10), facecolor='#f8f9fa')
        ax.set_facecolor('#ffffff')
        
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c']
        violation_counts.plot(kind='bar', stacked=True, color=colors, ax=ax, width=0.8, edgecolor='white', linewidth=2)
        
        for c in ax.containers:
            labels = [int(v.get_height()) if v.get_height() > 0 else '' for v in c]
            ax.bar_label(c, labels=[f'{v}' if v else '' for v in labels], 
                        label_type='center', color='white', weight='bold', fontsize=11, fontproperties=font)
        
        # ax.set_title(process_persian_text('روند تعداد و ترکیب تخلفات قانونی در طول زمان'), 
        #             fontproperties=font, size=18, weight='bold', pad=20, color='#2c3e50')
        ax.set_xlabel(process_persian_text('سال مالی'), fontproperties=font, size=20, weight='bold', color='#34495e')
        ax.set_ylabel(process_persian_text('تعداد موارد عدم رعایت'), fontproperties=font, size=25, weight='bold', color='#34495e')
        ax.tick_params(axis='x', rotation=0, labelsize=20)
        ax.tick_params(axis='y', labelsize=20)
        
        ax.grid(True, axis='y', linestyle='--', alpha=0.3, color='#bdc3c7')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#bdc3c7')
        ax.spines['bottom'].set_color('#bdc3c7')
        
        legend = ax.get_legend()
        # legend.set_title(process_persian_text('دسته اصلی تخلف'), prop=font)
        title_font = font.copy()
        title_font.set_size(16) 
        legend.set_title(process_persian_text('دسته اصلی ریسک'), prop=title_font)
        legend.set_frame_on(True)
        legend.set_loc('upper right')
        legend.get_frame().set_facecolor('#ffffff')
        legend.get_frame().set_edgecolor('#bdc3c7')
        legend.get_frame().set_linewidth(1.5)
        for text in legend.get_texts():
            text.set_text(process_persian_text(text.get_text()))
            text.set_fontproperties(font)
            text.set_fontsize(15)

        plt.subplots_adjust(right=0.82)

        return fig
    

    
    def plot_violations_sunburst(df):
        """نمودار Sunburst تخلفات - نسخه اصلاح شده با متن واضح"""
        
        sunburst_data = df.groupby(['دسته_اصلی', 'زیرشاخه']).size().reset_index(name='تعداد')

        fig = px.sunburst(
            sunburst_data,
            path=[px.Constant("تمام تخلفات"), 'دسته_اصلی', 'زیرشاخه'],
            values='تعداد',
            color='دسته_اصلی',
            # title='تحلیل ساختار و توزیع تخلفات قانونی',
            color_discrete_sequence=px.colors.qualitative.Set3,
            hover_data={'تعداد': True}
        )
        
        fig.update_layout(
            width=900,
            height=700,
            # title={
            #     'text': 'تحلیل ساختار و توزیع تخلفات قانونی',
            #     'y': 0.98,
            #     'x': 0.5,
            #     'xanchor': 'center',
            #     'yanchor': 'top',
            #     'font': {'size': 22, 'family': 'Tahoma', 'color': '#2c3e50'}
            # },
            font_family="Noto Naskh Arabic",
            font_size=13,
            margin=dict(t=80, l=40, r=40, b=40),
            paper_bgcolor='#f8f9fa',
            plot_bgcolor='#ffffff',
            # ✅ تنظیمات مهم برای نمایش صحیح hover
            hovermode='closest',
            hoverlabel=dict(
                bgcolor="white",
                font_size=20,
                font_family="Noto Naskh Arabic",
                align="right"
            )
        )
        
        fig.update_traces(
            textinfo="label",
            insidetextorientation='horizontal',  # ✅ افقی برای خوانایی بهتر
            marker=dict(
                line=dict(color='white', width=2.5)
            ),
            textfont=dict(
                size=20,  # ✅ فونت متوسط برای خوانایی بهتر
                family="Noto Naskh Arabic",
                color="black"
            ),
            # ✅ Hover template ساده و واضح با فارسی
            hovertemplate='<b style="font-family:Noto Naskh Arabic">%{label}</b><br>' +
                        '<span style="font-family:Noto Naskh Arabic">تعداد: %{value}</span><br>' +
                        '<span style="font-family:Noto Naskh Arabic">نسبت: %{percentRoot:.1%}</span>' +
                        '<extra></extra>',
            hoverlabel=dict(
                bgcolor="rgba(255,255,255,0.95)",
                bordercolor="#2c3e50",
                font=dict(family="Noto Naskh Arabic", size=13, color="black")
            )
        )
        
        return fig
    # ========================================================================
    # بخش اصلاح شده: پردازش همزمان فایل‌ها
    # ========================================================================

    class FinancialAnalyzer:
        """کلاس تحلیلگر مالی با پشتیبانی از پردازش همزمان"""
        
        def __init__(self):
            # Schema بدون تغییر
            self.response_schema = {
                "type": "object",
                "properties": {
                    "تحلیل_جامع_گزارش_حسابرسی": {
                        "type": "object",
                        "description": "ساختار اصلی که تحلیل کامل گزارش حسابرس مستقل و بازرس قانونی را در خود جای می‌دهد.",
                        "properties": {
                            "بخش۱_خلاصه_و_اطلاعات_کلیدی": {
                                "type": "object",
                                "description": "شامل اطلاعات اولیه گزارش و نتیجه‌گیری‌های اصلی در یک نگاه.",
                                "properties": {
                                    "نام_شرکت": {"type": "string", "description": "نام کامل شرکت از روی جلد گزارش."},
                                    "نام_حسابرس": {"type": "string", "description": "نام موسسه حسابرسی."},
                                    "دوره_مالی": {"type": "string", "description": "دوره مالی مورد رسیدگی، مثلا: 'سال مالی منتهی به ۲۹ اسفند ۱۳۹۸'."},
                                    "نوع_اظهارنظر": {
                                        "type": "string",
                                        "description": "یکی از موارد: مقبول، مشروط، مردود، عدم اظهارنظر.",
                                        "enum": ["مقبول", "مشروط", "مردود", "عدم اظهارنظر"]
                                    },
                                    "سطح_ریسک_کلی_بنا_به_گزارش": {
                                        "type": "string",
                                        "description": "سطح ریسک کلی استنباط شده از گزارش حسابرس مستقل و بازرس قانونی بنا به متن گزارش و شواهد و آماره های بیان شده از دیدگاه حسابرسی",
                                        "enum": ["پایین", "متوسط", "بالا", "بحرانی"]
                                    },
                                    "جزییات_سطح_ریسک_تعیین_شده": {
                                        "type": "string",
                                        "description": "جزییات و دلیل سطح ریسک کلی استنباط شده از گزارش."
                                    },
                                    "نکات_کلیدی_و_نتیجه_گیری": {
                                        "type": "array",
                                        "description": "آرایه‌ای از ۳ رشته شامل مهم‌ترین یافته‌ها و نتیجه‌گیری‌ها.",
                                        "items": {"type": "string"}
                                    }
                                },
                                "required": [
                                    "نام_شرکت", "نام_حسابرس", "دوره_مالی", "نوع_اظهارنظر",
                                    "سطح_ریسک_کلی_بنا_به_گزارش", "جزییات_سطح_ریسک_تعیین_شده",
                                    "نکات_کلیدی_و_نتیجه_گیری"
                                ]
                            },
                            "بخش۲_تجزیه_تحلیل_گزارش": {
                                "type": "object",
                                "description": "تجزیه و تحلیل ساختاریافته متن گزارش، بند به بند.",
                                "properties": {
                                    "بند_اظهارنظر": {
                                        "type": "object",
                                        "properties": {
                                            "نوع": {"type": "string"},
                                            "خلاصه_دلایل": {"type": "string"}
                                        },
                                        "required": ["نوع", "خلاصه_دلایل"]
                                    },
                                    "بند_مبانی_اظهارنظر": {
                                        "type": "object",
                                        "properties": {
                                            "موضوعیت_دارد": {"type": "boolean"},
                                            "موارد_مطرح_شده": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "شماره_مورد": {"type": "integer"},
                                                        "عنوان": {"type": "string"},
                                                        "شرح": {"type": "string"},
                                                        "نوع_دلیل": {
                                                            "type": "string",
                                                            "enum": ["محدودیت در رسیدگی", "انحراف از استانداردهای حسابداری", "سایر"]
                                                        }
                                                    },
                                                    "required": ["شماره_مورد", "عنوان", "شرح", "نوع_دلیل"]
                                                }
                                            }
                                        },
                                        "required": ["موضوعیت_دارد"]
                                    },
                                    "بند_تاکید_بر_مطالب_خاص": {
                                        "type": "object",
                                        "properties": {
                                            "موضوعیت_دارد": {"type": "boolean"},
                                            "موارد_مطرح_شده": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "ارجاع": {
                                                            "type": "object",
                                                            "properties": {
                                                                "شماره_بند": {
                                                                    "type": "string",
                                                                    "description": "شماره بند مربوطه در گزارش حسابرس مستقل و بازرس قانونی .بین بند ها , قرار بده مانند ۲,۶"
                                                                    },
                                                                "شماره_صفحه": {
                                                                    "type": "string",
                                                                "description": "شماره صفحه مربوطه در گزارش حسابرس مستقل و بازرس قانونی.چنانچه این مورد در چند بند به ان اشاره شده صفحات منطبق با بند را به ترتیب بند برگردان بین صفحات , قرار بده مانند ۱,۵"
                                                                    }
                                                            },
                                                            "required": ["شماره_بند", "شماره_صفحه"]
                                                        },
                                                        "عنوان": {"type": "string"},
                                                        "شرح": {"type": "string"},
                                                        "ریسک_برجسته_شده": {"type": "string"},
                                                        "دسته_اصلی_ریسک": {
                                                            "type": "string",
                                                            "enum": ["ریسک اعتباری", "ریسک بازار", "ریسک نقدینگی", "ریسک عملیاتی", "ریسک قانونی و تطبیق", "ریسک استراتژیک", "ریسک شهرت"]
                                                        },
                                                        "زیرشاخه_ریسک": {
                                                            "type": "string",
                                                            "description": """ زیرشاخه دقیق ریسک شناسایی شده مرتبط با دسته اصلی شناسایی شده .(دقیقا از این مصادیق استفاده شود. مصادق منطبق با الگوی دسته_اصلی:[زیرشاخه ها] مانند 
                                                                                                                                                                                            
                                                                            ۱. زیرشاخه‌های ریسک اعتباری:
                                                                            [ریسک نکول ,
                                                                            ریسک تمرکز ,
                                                                            ریسک طرف قرارداد ,
                                                                            ریسک کشور ,
                                                                            ریسک تضعیف وثایق ,
                                                                            ریسک وصول مطالبات ]
                                                                            ,

                                                                            ۲. زیرشاخه‌های ریسک بازار:
                                                                            [ریسک نرخ ارز ,
                                                                            ریسک نرخ سود ,
                                                                            ریسک قیمت کالا ,
                                                                            ریسک قیمت سهام ,
                                                                            ریسک نوسان ارزش سرمایه‌گذاری‌ها ]
                                                                            ,

                                                                            ۳. زیرشاخه‌های ریسک نقدینگی:
                                                                            [ریسک تامین مالی ,
                                                                            ریسک نقدشوندگی بازار ,
                                                                            ریسک تسویه با نهادهای حاکمیتی ]
                                                                            ,

                                                                            ۴. زیرشاخه‌های ریسک عملیاتی:
                                                                            [ریسک فرآیندهای داخلی ,
                                                                            ریسک فناوری اطلاعات و امنیت سایبری ,
                                                                            ریسک منابع انسانی ,
                                                                            ریسک تقلب ,
                                                                            ریسک رویدادهای خارجی ,
                                                                            ریسک مدل ,
                                                                            ریسک عدم کفایت پوشش بیمه‌ای ]
                                                                            ,

                                                                            ۵. زیرشاخه‌های ریسک قانونی و تطبیق:
                                                                            [ریسک دعاوی حقوقی ,
                                                                            ریسک عدم رعایت مقررات,
                                                                            ریسک قراردادها ,
                                                                            ریسک مالیاتی ,
                                                                            ریسک پولشویی و تامین مالی تروریسم ,
                                                                            ریسک حاکمیت شرکتی ]
                                                                            ,
                                                                            ۶. زیرشاخه‌های ریسک استراتژیک:
                                                                            [ریسک رقابت ,
                                                                            ریسک تغییرات تکنولوژی ,
                                                                            ریسک تصمیمات مدیریتی ,
                                                                            ریسک پروژه‌ها و سرمایه‌گذاری‌های کلان,
                                                                            ریسک ادغام و تملیک ,
                                                                            ریسک تغییرات کلان اقتصادی ]

                                                                            ۷. زیرشاخه‌های ریسک شهرت:
                                                                            [ریسک رضایت مشتری ,
                                                                            ریسک وجهه عمومی ,
                                                                            ریسک روابط با ذینفعان ],
                                                                            8.سایر
                                                            """,

                                                        }
                                                    },
                                                    "required": ["ارجاع", "عنوان", "شرح", "ریسک_برجسته_شده", "دسته_اصلی_ریسک", "زیرشاخه_ریسک"]
                                                }
                                            }
                                        },
                                        "required": ["موضوعیت_دارد"]
                                    },
                                    "گزارش_رعایت_الزامات_قانونی": {
                                        "type": "object",
                                        "properties": {
                                            "موضوعیت_دارد": {"type": "boolean"},
                                            "تخلفات": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "ارجاع": {
                                                            "type": "object",
                                                            "properties": {
                                                               "شماره_بند": {
                                                                "type": "string",
                                                                "description": "شماره بند مربوطه در گزارش حسابرس مستقل و بازرس قانونی .بین بند ها , قرار بده مانند ۲,۶"
                                                            },
                                                            "شماره_صفحه": {
                                                                "type": "string",
                                                                "description": "شماره صفحه مربوطه در گزارش حسابرس مستقل و بازرس قانونی.چنانچه این مورد در چند بند به ان اشاره شده صفحات منطبق با بند را به ترتیب بند برگردان بین صفحات , قرار بده مانند ۱,۵"
                                                            }
                                                            },
                                                            "required": ["شماره_بند", "شماره_صفحه"]
                                                        },
                                                        "عنوان_تخلف": {"type": "string"},
                                                        "شرح": {"type": "string"},
                                                        "مبانی_قانونی_و_استانداردها": {
                                                            "type": "array",
                                                            "items": {
                                                                "type": "string",
                                                                "enum": [
                                                                    "قانون پولی و بانکی کشور",
                                                                    "قانون عملیات بانکی بدون ربا‌ً",
                                                                    "آیین نامه ها و دستورالعمل‌های بانک مرکزی (مهمترین بخش)",
                                                                    "اساسنامه بانک",
                                                                    "قانون تجارت (در موارد مرتبط)",
                                                                    "استانداردهای حسابداری",
                                                                    "استانداردهای حسابرسی"
                                                                ]
                                                            }
                                                        },
                                                        "دسته_اصلی": {
                                                            "type": "string",
                                                            "description": "دسته اصلی تخلف بر اساس منشأ قانون.اگر یک تخلف به چند قانون مربوط است، اولویت با دسته‌ای است که خاص‌تر و مهم‌تر است. ",
                                                            "enum": [
                                                            "الزامات نهاد ناظر بانکی (بانک مرکزی)",
                                                            "الزامات بازار سرمایه (سازمان بورس)",
                                                            "قوانین حاکمیتی و شرکتی",
                                                            "قوانین مالیاتی، بیمه و بودجه",
                                                            "قوانین مبارزه با جرائم مالی",
                                                            "سایر قوانین و مقررات"
                                                            ]
                                                        },
                                                        "زیرشاخه": {
                                                            "type": "string",
                                                            "description": """ زیرشاخه دقیق تخلف شناسایی شده مرتبط با دسته اصلی شناسایی شده .(دقیقا از این مصادیق استفاده شود. مصادق منطبق با الگوی دسته_اصلی:[زیرشاخه ها] مانند 
                                                                :الزامات نهاد ناظر بانکی (بانک مرکزی)
                                                                [ کفایت سرمایه و مدیریت سرمایه,
                                                                تسهیلات و تعهدات کلان,
                                                                معاملات با اشخاص وابسته,
                                                                طبقه‌بندی دارایی‌ها و ذخیره‌گیری,
                                                                مدیریت نقدینگی و سپرده قانونی,
                                                                نرخ سود و کارمزد خدمات,
                                                                الزامات ارزی,
                                                                واگذاری اموال و دارایی‌های مازاد,
                                                                الزامات صندوق ضمانت سپرده‌هام],

                                                                الزامات بازار سرمایه (سازمان بورس):
                                                                [افشای اطلاعات,
                                                                حاکمیت شرکتی (دستورالعمل بورس),
                                                                تکالیف مجامع عمومی (مربوط به بورس),
                                                                معاملات با اشخاص وابسته (ضوابط بورس)],

                                                                قوانین حاکمیتی و شرکتی:
                                                                [نقض مفاد اساسنامه,
                                                                نقض قانون تجارت,
                                                                تکالیف ثبت شرکت‌ها,]
                                                                    
                                                                قوانین مالیاتی، بیمه و بودجه:
                                                                [مالیات عملکرد و تکلیفی,
                                                                مالیات بر ارزش افزوده (VAT),
                                                                بیمه تامین اجتماعی,
                                                                قوانین بودجه سنواتی و توسعه],
                                                                قوانین مبارزه با جرائم مالی:
                                                                [مبارزه با پولشویی (AML),
                                                                مبارزه با تامین مالی تروریسم (CFT)],
                                                                سایر قوانین و مقررات:
                                                                [قانون کار,
                                                                قوانین شهرداری و محیط زیست,
                                                                حقوق مالکیت فکری,
                                                                سایر
                                                                ]
                                                            """,
                                                            
                                                        },

                                                        },
                                                        "required": [
                                                        "ارجاع",
                                                        "عنوان_تخلف",
                                                        "شرح",
                                                        "مبانی_قانونی_و_استانداردها",
                                                        "دسته_اصلی",
                                                        "زیرشاخه"
                                                        ]

                                                }
                                            }
                                        },
                                        "required": ["موضوعیت_دارد"]
                                    }
                                }
                            },
                            "بخش۳_چک_لیست_موضوعی": {
                                "type": "array",
                                "description":" باید تمام موضوع های زیر را چک کنید و در خروجی بیاورید هم مواردی که در گزارش آمده هم مواردی که نیامده",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "موضوع": {
                                            "type": "string",
                                            "enum": [
                     # 🎯 اولویت خیلی بالا
                                                "کفایت سرمایه",
                                                "نسبت‌ها در چارچوب بازل",
                                                "ریسک نقدینگی",
                                                "مدیریت دارایی و بدهی (ALM)",
                                                "ریسک نرخ بهره",
                                                "تمرکز ریسک اعتباری",
                                                "ذخیره‌گیری (کلی)",

                                                # 🔥 اولویت بالا
                                                "صورت جریان وجوه نقد",
                                                "کنترل‌های داخلی و حسابرسی داخلی",
                                                "حاکمیت شرکتی",
                                                "اوراق بهادار و سرمایه‌گذاری‌ها",
                                                "تسعیر ارز و عملیات خارجی",
                                                "تعهدات ارزی و اختلاف با بانک مرکزی",
                                                "ذخیره مطالبات مشکوک‌الوصول",
                                                "مطالبات مشکوک‌الوصول",
                                                "تسهیلات و اعتبارات",
                                                "سرمایه‌گذاری در شرکت‌های وابسته",
                                                "کاهش ارزش دارایی‌ها",
                                                "افشای ریسک‌های عملیاتی",
                                                "نسبت‌های بدهی و نقدینگی",
                                                "نسبت کفایت سرمایه",
                                                "معاملات با اشخاص وابسته",
                                                "تداوم فعالیت",
                                                "انطباق با مقررات ضدپولشویی (AML/CFT)",

                                                # # ⚙️ اولویت متوسط
                                                "ذخیره مزایای پایان خدمت کارکنان",
                                                "ریسک شهرت",
                                                "ذخیره مالیات بر درآمد",
                                                "حقوق صاحبان سهام",
                                                "سیستم‌های اطلاعاتی و فناوری",
                                                "انطباق با استانداردهای بین‌المللی",
                                                "پوشش بیمه‌ای دارایی‌ها",
                                                "دعاوی و جرائم حقوقی",
                                                "کیفیت افشای اطلاعات",
                                                "رویدادهای بعد از تاریخ ترازنامه",
                                                "تغییر رویه‌های حسابداری",
                                                "بدهی‌های احتمالی",
                                                "نسبت‌های سودآوری",
                                                "مالیات و جرائم مالیاتی",
                                                "سود سهام دولت",
                                                "عدم دریافت تأییدیه‌های حسابداری",
                                                "ذخیره دعاوی حقوقی",
                                                "تهاتر (Barter)",
                                                "صفحه امضا های سازمان حسابرسی"
                                            ]
                                        },
                                        "در_گزارش_آمده": {"type": "boolean"},
                                        "وضعیت": {
                                            "type": "string",
                                            "enum": [
                                                "مصداق ندارد", "بررسی شده - ریسک خاصی گزارش نشده",
                                                "مسئله کلیدی منجر به اظهارنظر مشروط", "ریسک بحرانی"
                                            ]
                                        },
                                        "جزئیات": {"type": "string"},
                                        "ارجاع": {
                                            "type": "object",
                                            "properties": {
                                                "شماره_بند": {
                                                "type": "string",
                                                "description": "شماره بند مربوطه در گزارش حسابرس مستقل و بازرس قانونی .بین بند ها , قرار بده مانند ۲,۶"
                                            },
                                            "شماره_صفحه": {
                                                "type": "string",
                                                "description": "شماره صفحه مربوطه در گزارش حسابرس مستقل و بازرس قانونی.چنانچه این مورد در چند بند به ان اشاره شده صفحات منطبق با بند را به ترتیب بند برگردان بین صفحات , قرار بده مانند ۱,۵"
                                            }
                                            }
                                        }
                                    },
                                    "required": ["موضوع", "در_گزارش_آمده", "وضعیت", "جزئیات", "ارجاع"]
                                }
                            }
                        }
                    }
                },
                "required": ["تحلیل_جامع_گزارش_حسابرسی"]
            }
        
        def extract_table_from_page(self, file_content: bytes, filename: str, max_retries: int = 5,  selected_model: str = None) -> Dict:

            prompt =  """لطفاً گزارش حسابرس را تحلیل کنید. نکته بسیار مهم برای بخش۳_چک_لیست_موضوعی:
            - باید تمام  موضوع ها را چک کنید و در خروجی بیاورید
            - برای هر موضوع، فیلد "در_گزارش_آمده" را مشخص کنید (true یا false)
            - همه موضوع ها باید در آرایه بخش۳_چک_لیست_موضوعی باشند"""
            
            # ✅ اگر مدل پاس نشده بود، از پیش‌فرض استفاده کن
            if selected_model is None:
                selected_model = 'gemini-2.5-pro'
                logger.warning(f"⚠️ No model provided to extract_table_from_page, using default: {selected_model}")
            

            # ✅ نمایش لاگ مدل انتخابی
            logger.info(f"🎯 Using model: {selected_model} for {filename}")

            for attempt in range(max_retries):
                try:
                    client, current_api_key = get_client_with_retry()
                    logger.info(f"Processing {filename} with model {selected_model} - Attempt {attempt + 1}")
                    response = client.models.generate_content(
                        model=selected_model,
                        contents=[types.Part.from_bytes(data=file_content, mime_type="application/pdf"), prompt],
                        config={
                            'system_instruction': "شما تحلیلگر مالی هستید.",
                            "response_mime_type": "application/json",
                            "response_schema": self.response_schema,
                            "temperature": 0.5
                        }
                    )
                    if not response or not response.text:
                        raise ValueError("API response was empty")
                    data = json.loads(response.text)
                    api_key_manager.mark_success(current_api_key)
                    logger.info(f"Successfully processed {filename}")
                    return data
                except Exception as e:
                    logger.error(f"Error: {str(e)}")
                    api_key_manager.mark_failure(current_api_key)
                    if attempt < max_retries - 1:
                        time.sleep(min(15, (2 ** attempt)))
                    else:
                        raise
            raise Exception(f"Failed after {max_retries} attempts")

    # ========================================================================
    # ✅ تابع جدید: پردازش همزمان با ThreadPoolExecutor
    # ========================================================================

    def process_single_file(analyzer, file_data, index, total, attempt=1, max_attempts=3, selected_model=None):  # 👈 پارامتر جدید
        """
        پردازش یک فایل با قابلیت retry خودکار
        
        Args:
            analyzer: نمونه FinancialAnalyzer
            file_data: داده فایل (dict یا file object)
            index: شماره فایل
            total: تعداد کل فایل‌ها
            attempt: تلاش فعلی (1، 2، 3)
            max_attempts: حداکثر تعداد تلاش
            selected_model: مدل انتخابی توسط کاربر  # 👈 جدید
        
        Returns:
            tuple: (index, filename, result, error, needs_retry)
        """
        filename = file_data['name'] if isinstance(file_data, dict) else file_data.name
        file_content = file_data['content'] if isinstance(file_data, dict) else file_data.getvalue()
        
        
        # ✅ اگر مدل پاس نشده، از مقدار پیش‌فرض استفاده کن
        if selected_model is None:
            selected_model = 'gemini-2.5-pro'
            logger.warning(f"⚠️ No model provided to process_single_file, using default: {selected_model}")
        
        try:
            logger.info(f"🔄 Processing {filename} with model {selected_model} - Attempt {attempt}/{max_attempts}")
            
            # ✅ پاس دادن مدل به تابع
            result = analyzer.extract_table_from_page(
                file_content, 
                filename, 
                selected_model=selected_model  # 👈 پاس صریح مدل
            )
            return (index, filename, result, None, False)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Failed to process {filename} (Attempt {attempt}): {error_msg}")
            
            needs_retry = attempt < max_attempts and is_retryable_error(error_msg)
            
            return (index, filename, None, error_msg, needs_retry)

    def is_retryable_error(error_msg: str) -> bool:
        """
        تشخیص اینکه خطا قابل retry است یا نه
        
        خطاهای قابل retry:
        - Timeout
        - Rate limit (429)
        - Server error (500, 503)
        - Network errors
        - API overloaded
        
        خطاهای غیرقابل retry:
        - Invalid file format
        - Authentication error (403)
        - File too large
        """
        retryable_patterns = [
            'timeout',
            'timed out',
            'rate limit',
            '429',
            '500',
            '503',
            'server error',
            'network',
            'connection',
            'overloaded',
            'temporarily unavailable',
            'try again later',
            'unavailable'
        ]
        
        error_lower = error_msg.lower()
        return any(pattern in error_lower for pattern in retryable_patterns)
    
 
    # ========================================================================
    # ✅ تابع اصلاح شده: create_processing_section
    # ========================================================================

    def create_processing_section(uploaded_files):
        """
        بخش پردازش فایل‌ها با مدیریت حالت کامل (آماده، در حال پردازش، انجام شده)
        و قابلیت تحلیل مجدد - با استفاده از نام یکسان session_state
        """
        # مقداردهی اولیه حالت‌ها در صورت عدم وجود
        if 'processing_active' not in st.session_state:
            st.session_state.processing_active = False
        if 'results' not in st.session_state:  # ✅ استفاده از 'results' به جای 'processing_results'
            st.session_state.results = None

        if not uploaded_files:
            st.session_state.results = None  # پاک کردن نتایج اگر فایل‌ها حذف شوند
            return

        # =========================================================================
        # بخش 1: نمایش کارت‌های آماری (این بخش همیشه نمایش داده می‌شود)
        # =========================================================================
        with st.container():
            st.subheader("🚀 وضعیت پردازش")
            st.divider()

            col1, col2, col3 = st.columns(3)
            total_size_mb = sum(
                len(f['content']) if isinstance(f, dict) else f.size
                for f in uploaded_files
            ) / (1024 * 1024)

            with col1:
                st.markdown(f'''
                    <div class="metric-modern">
                        <p>تعداد فایل‌ها</p>
                        <div class="metric-value-box">
                            <div class="metric-value">{len(uploaded_files)}</div>
                        </div>
                    </div>
                ''', unsafe_allow_html=True)
                
            with col2:
                st.markdown(f'''
                    <div class="metric-modern">
                        <p>حجم کل</p>
                        <div class="metric-value-box">
                            <div class="metric-value">{total_size_mb:.1f} MB</div>
                        </div>
                    </div>
                ''', unsafe_allow_html=True)

            with col3:
                # تعیین وضعیت بر اساس حالت‌های مختلف
                if st.session_state.results:
                    status_text = "تکمیل شد ✅"
                    status_class = "metric-status-done"
                elif st.session_state.processing_active:
                    status_text = "در حال پردازش 🔄"
                    status_class = "metric-status-processing"
                else:
                    status_text = "آماده 🟢"
                    status_class = "metric-status-ready"
                
                st.markdown(f'''
                    <div class="metric-modern {status_class}">
                        <p>وضعیت</p>
                        <div class="metric-value-box">
                            <div class="metric-value">{status_text}</div>
                        </div>
                    </div>
                ''', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # =========================================================================
            # بخش 2: دکمه‌ها و منطق پردازش (بر اساس حالت فعلی)
            # =========================================================================

            # حالت 1: پردازش انجام شده و نتایج موجود است
            if st.session_state.results:
                # محاسبه تعداد فایل‌های موفق
                successful_count = len([r for r in st.session_state.results if r and 'error' not in r[1]])
                failed_count = len(st.session_state.results) - successful_count
                
                # نمایش پیام موفقیت با جزئیات
                if failed_count == 0:
                    st.success(f"🎉 تحلیل با موفقیت تکمیل شد! {successful_count} فایل تحلیل شد. نتایج در تب‌های دیگر قابل مشاهده است.")
                else:
                    st.warning(f"⚠️ تحلیل تکمیل شد: {successful_count} فایل موفق، {failed_count} فایل ناموفق. نتایج در تب‌های دیگر قابل مشاهده است.")
                
                # دکمه تحلیل مجدد
                col_btn1, col_btn2 = st.columns([1, 3])
                with col_btn1:
                    if st.button("🔄 تحلیل مجدد", type="primary", use_container_width=True):
                        # پاک کردن نتایج قبلی و ریست کردن حالت برای شروع مجدد
                        st.session_state.results = None
                        st.session_state.processing_active = False
                        st.rerun()

            # حالت 2: پردازش در حال انجام است
            elif st.session_state.processing_active:
                st.warning("⚠️ پردازش در حال اجرا است. لطفاً منتظر بمانید...")
                info_html = """
                    <div style="
                        background-color: #e6f3ff; 
                        border-radius: 10px; 
                        padding: 1rem 1.5rem; 
                        margin-bottom: 1rem;
                        direction: rtl; 
                        border-right: 6px solid #1c83e1;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    ">
                        <h4 style="margin-top: 0; margin-bottom: 0.75rem; font-weight: bold;">💡 نکته مهم:</h4>
                        <ul style="padding-right: 25px; margin-bottom: 0;">
                            <li style="margin-bottom: 8px;">پردازش در پس‌زمینه در حال انجام است.</li>
                            <li style="margin-bottom: 8px;">پس از اتمام، نتایج به صورت خودکار در تب‌های دیگر نمایش داده می‌شود.</li>
                            <li style="margin-bottom: 8px;">در صورت عدم پردازش فایل میتوانید از دکمه تحلیل مجدد استفاده کنید.</li>
                            <li>چنانچه در نتایج فایل‌ها خطای 429 مشاهده کردید باید کلیدهای خود را تغییر دهید.</li>
                        </ul>
                    </div>
                    """
                st.markdown(info_html, unsafe_allow_html=True)
                # در این حالت، تابع اصلی پردازش فراخوانی می‌شود
                try:
                    results = process_files_concurrent_smart(uploaded_files)
                    st.session_state.results = results
                    st.session_state.processing_active = False
                    st.rerun()  # بازخوانی صفحه برای نمایش حالت "انجام شده"
                except Exception as e:
                    st.session_state.processing_active = False
                    st.session_state.results = None
                    st.error(f"❌ خطای غیرمنتظره در حین پردازش: {str(e)}")
                    logger.error(f"Critical processing error: {traceback.format_exc()}")
                    st.rerun()

            # حالت 3: آماده برای شروع پردازش
            else:
                if st.button("🚀 شروع تحلیل", type="primary", use_container_width=True):
                    st.session_state.processing_active = True
                    st.session_state.results = None  # اطمینان از پاک بودن نتایج قبلی
                    st.rerun()


    def get_risk_class(risk_level):
        risk_classes = {'پایین': 'risk-low', 'متوسط': 'risk-medium', 'بالا': 'risk-high', 'بحرانی': 'risk-critical'}
        return risk_classes.get(risk_level, '')

    def flatten_reference_data(df):
        if 'ارجاع' in df.columns:
            df['شماره_بند'] = df['ارجاع'].apply(lambda x: x.get('شماره_بند', '') if isinstance(x, dict) else '')
            df['شماره_صفحه'] = df['ارجاع'].apply(lambda x: x.get('شماره_صفحه', '') if isinstance(x, dict) else '')
            df = df.drop('ارجاع', axis=1)
        return df

    def flatten_array_fields(df):
        for col in df.columns:
            df[col] = df[col].apply(lambda x: ", ".join(map(str, x)) if isinstance(x, list) else x)
        return df

    # ========================================================================
    # بخش 9: توابع UI
    # ========================================================================

    def create_header():
        st.markdown('<div class="modern-header"><h1>📊 تحلیلگر هوشمند صورت‌های مالی</h1></div>', unsafe_allow_html=True)

    def create_file_upload_section():
        st.markdown('<div class="modern-card"> <h2>📁 بارگذاری فایل‌ها</h2></div>', unsafe_allow_html=True)
        st.divider()
        upload_method = st.radio("روش بارگذاری:", ["فایل‌های جداگانه", "پوشه ZIP"], horizontal=True)
        uploaded_files = []
        if upload_method == "فایل‌های جداگانه":
            uploaded_files = st.file_uploader("فایل های PDF خود را اینجا بارگذاری کنید", type=['pdf'], accept_multiple_files=True)
        else:
            zip_file = st.file_uploader("فایل ZIP شامل PDF ها را انتخاب کنید", type=['zip'])
            if zip_file:
                try:
                    with zipfile.ZipFile(zip_file, 'r') as z:
                        uploaded_files = [{'name': os.path.basename(f.filename), 'content': z.read(f.filename)} for f in z.infolist() if f.filename.lower().endswith('.pdf')]
                    if uploaded_files:
                        st.success(f'✅ {len(uploaded_files)} فایل PDF استخراج شد')
                except Exception as e:
                    st.error(f'❌ خطا: {e}')
        return uploaded_files

    def process_files(uploaded_files):
        analyzer = FinancialAnalyzer()
        results = []
        st.markdown('<div class="modern-card"><h3>در حال پردازش...</h3></div>', unsafe_allow_html=True)
        progress_bar = st.progress(0)
        status_placeholder = st.empty()
        total_files = len(uploaded_files)
        start_time = time.time()
        for i, file in enumerate(uploaded_files):
            filename = file['name'] if isinstance(file, dict) else file.name
            file_content = file['content'] if isinstance(file, dict) else file.getvalue()
            status_placeholder.info(f'📄 در حال تحلیل فایل {i+1} از {total_files}: {filename}')
            try:
                result = analyzer.extract_table_from_page(file_content, filename, selected_model=st.session_state.selected_model)
                results.append((filename, result))
                status_placeholder.success(f'✅ **{filename}** با موفقیت تحلیل شد.')
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to process {filename}: {error_msg}\n{traceback.format_exc()}")
                results.append((filename, {"error": f"خطا در تحلیل: {error_msg}"}))
                status_placeholder.error(f'❌ خطا در تحلیل **{filename}**: {error_msg[:100]}...')
            progress_bar.progress((i + 1) / total_files)
        total_duration = time.time() - start_time
        status_placeholder.success(f'🎉 تحلیل تکمیل شد! {total_files} فایل در {total_duration/60:.1f} دقیقه پردازش شد.')
        return results
    



    @st.cache_data
    def convert_to_excel(results):

        def style_excel_file(file_path):
            wb = load_workbook(file_path)

            # 🎨 تعریف استایل عمومی فونت و وسط چین
            base_style = NamedStyle(name="base_style")
            base_style.font = Font(name="Calibri", size=12)
            base_style.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            # 🎨 استایل هدر
            header_fill = PatternFill(start_color="CCC0DA", end_color="CCC0DA", fill_type="solid")
            header_font = Font(name="Calibri", size=12, bold=True)

            # 🎨 رنگ ردیف‌های یکی در میان
            row_fill_alt = PatternFill(start_color="F7F7F7", end_color="F7F7F7", fill_type="solid")


            for ws in wb.worksheets:

                # ست کردن استایل کل شیت
                for row in ws.iter_rows():
                    for cell in row:
                        cell.style = base_style

                # 📌 استایل برای هدرها (ردیف اول)
                # استایل هدر (ردیف 1)
                for cell in ws[1]:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

                # ✅ افزایش ارتفاع هدر
                ws.row_dimensions[1].height = 35  
     


                # تنظیم عرض ستون‌ها با محدودیت برای ستون‌های متنی طولانی
                long_text_columns = [ "نکات_کلیدی_و_نتیجه_گیری", "جزئیات", "شرح", "خلاصه_دلایل", "جزییات_سطح_ریسک_تعیین_شده"]

                for col in ws.columns:
                    max_length = 0
                    column = get_column_letter(col[0].column)
                    header = str(col[0].value)

                    # محاسبه طول داده‌ها
                    for cell in col:
                        try:
                            max_length = max(max_length, len(str(cell.value)))
                        except:
                            pass

                    # ✅ شرط: اگر ستون جزو ستون‌های توضیحی بود → محدودیت اعمال کن
                    if any(x in header for x in long_text_columns):
                        ws.column_dimensions[column].width = min(max(max_length, 20), 40)
                    else:
                        # ستون‌ها کمی عریض‌تر از حالت قبلی
                        ws.column_dimensions[column].width = max(max_length + 3, 15)

                # 🟦 اعمال رنگ یکی در میان برای ردیف‌ها
                for r in range(2, ws.max_row+1):
                    if r % 2 == 0:
                        for cell in ws[r]:
                            cell.fill = row_fill_alt
                           # ✅ تعریف Border
                thin_border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
                # ✅ اعمال Border روی کل سلول‌های شیت
                for row in ws.iter_rows():
                    for cell in row:
                        cell.border = thin_border


            wb.save(file_path)

 # =======================
    # ✅ بخش ساخت فایل اکسل
    # =======================

        temp_dir = tempfile.mkdtemp()
        excel_files = []
        
        for filename, data in results:
            try:
                if "error" in data:
                    continue
                
                report = data["تحلیل_جامع_گزارش_حسابرسی"]
                
                # ✅ استخراج سال مالی
                try:
                    company_name = report["بخش۱_خلاصه_و_اطلاعات_کلیدی"]["نام_شرکت"]
                    financial_year = report["بخش۱_خلاصه_و_اطلاعات_کلیدی"]["دوره_مالی"]
                    
                    year_match = re.search(r'(\d{4})', financial_year)
                    year = year_match.group(1) if year_match else "Unknown"
                    
                    clean_company_name = re.sub(r'[\\/:"*?<>|]+', "", company_name).strip()
                    if not clean_company_name:
                        clean_company_name = f"Company_{len(excel_files) + 1}"
                    
                    excel_filename = f"{clean_company_name}_{year}.xlsx"
                    
                except:
                    year = "Unknown"
                    excel_filename = f"Company_{len(excel_files) + 1}.xlsx"
                
                output_file = os.path.join(temp_dir, excel_filename)
                
                with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
                    
                    # ========================================
                    # بخش 1: خلاصه و اطلاعات کلیدی
                    # ========================================
                    try:
                        part1 = report["بخش۱_خلاصه_و_اطلاعات_کلیدی"]
                        df1 = pd.DataFrame.from_dict({
                            k: [v] if not isinstance(v, list) else [", ".join(v)] 
                            for k, v in part1.items()
                        })
                        # ✅ اضافه کردن ستون year
                        df1['year'] = year
                        df1.to_excel(writer, sheet_name="بخش1_خلاصه", index=False)
                    except Exception as e:
                        logger.warning(f"خطا در پردازش بخش 1: {str(e)}")
                    
                    # ========================================
                    # بخش 2: تجزیه تحلیل گزارش
                    # ========================================
                    try:
                        part2 = report.get("بخش۲_تجزیه_تحلیل_گزارش", {})
                        
                        # شیت: بند اظهارنظر
                        if "بند_اظهارنظر" in part2:
                            df_opinion = pd.DataFrame([part2["بند_اظهارنظر"]])
                            # ✅ اضافه کردن ستون year
                            df_opinion['year'] = year
                            df_opinion.to_excel(writer, sheet_name="بند_اظهارنظر", index=False)
                        
                        # شیت: بند مبانی اظهارنظر
                        if "بند_مبانی_اظهارنظر" in part2:
                            basis_data = part2["بند_مبانی_اظهارنظر"]
                            if basis_data.get("موضوعیت_دارد", False) and "موارد_مطرح_شده" in basis_data:
                                df_basis = pd.DataFrame(basis_data["موارد_مطرح_شده"])
                                df_basis = flatten_reference_data(df_basis)
                                df_basis = flatten_array_fields(df_basis)
                                # ✅ اضافه کردن ستون year
                                df_basis['year'] = year
                            else:
                                df_basis = pd.DataFrame([{"موضوعیت_دارد": False, "year": year}])
                            df_basis.to_excel(writer, sheet_name="بند_مبانی_اظهارنظر", index=False)
                        
                        # شیت: بند تاکید بر مطالب خاص
                        if "بند_تاکید_بر_مطالب_خاص" in part2:
                            emphasis_data = part2["بند_تاکید_بر_مطالب_خاص"]
                            if emphasis_data.get("موضوعیت_دارد", False) and "موارد_مطرح_شده" in emphasis_data:
                                df_emphasis = pd.DataFrame(emphasis_data["موارد_مطرح_شده"])
                                df_emphasis = flatten_reference_data(df_emphasis)
                                df_emphasis = flatten_array_fields(df_emphasis)
                                # ✅ اضافه کردن ستون year
                                df_emphasis['year'] = year
                                # ✅ اضافه کردن flag موضوعیت
                                df_emphasis['موضوعیت_دارد'] = True
                            else:
                                df_emphasis = pd.DataFrame([{"موضوعیت_دارد": False, "year": year}])
                            df_emphasis.to_excel(writer, sheet_name="بند_تاکید_بر_مطالب_خاص", index=False)
                        
                        # شیت: گزارش رعایت الزامات قانونی
                        if "گزارش_رعایت_الزامات_قانونی" in part2:
                            legal_data = part2["گزارش_رعایت_الزامات_قانونی"]
                            if legal_data.get("موضوعیت_دارد", False) and "تخلفات" in legal_data:
                                violations = legal_data["تخلفات"]
                                processed_violations = []
                                
                                for violation in violations:
                                    processed_violation = violation.copy()
                                    # تبدیل لیست به رشته
                                    if "مبانی_قانونی_و_استانداردها" in processed_violation:
                                        processed_violation["مبانی_قانونی_و_استانداردها"] = ", ".join(
                                            processed_violation["مبانی_قانونی_و_استانداردها"]
                                        )
                                    processed_violations.append(processed_violation)
                                
                                df_legal = pd.DataFrame(processed_violations)
                                df_legal = flatten_reference_data(df_legal)
                                df_legal = flatten_array_fields(df_legal)
                                # ✅ اضافه کردن ستون year
                                df_legal['year'] = year
                                # ✅ اضافه کردن flag موضوعیت
                                df_legal['موضوعیت_دارد'] = True
                            else:
                                df_legal = pd.DataFrame([{"موضوعیت_دارد": False, "year": year}])
                            df_legal.to_excel(writer, sheet_name="گزارش_قانونی", index=False)
                    
                    except Exception as e:
                        logger.warning(f"خطا در پردازش بخش 2: {str(e)}")
                    
                    # ========================================
                    # بخش 3: چک لیست موضوعی
                    # ========================================
                    try:
                        if "بخش۳_چک_لیست_موضوعی" in report:
                            part3 = report["بخش۳_چک_لیست_موضوعی"]
                            df3 = pd.DataFrame(part3)
                            df3 = flatten_reference_data(df3)
                            df3 = flatten_array_fields(df3)
                            # ✅ اضافه کردن ستون year
                            df3['year'] = year
                            df3.to_excel(writer, sheet_name="بخش3_چک_لیست", index=False)
                            
                    except Exception as e:
                        logger.warning(f"خطا در پردازش بخش 3: {str(e)}")
                           
                           
                 # ✅ اعمال استایل بعد از ذخیره فایل
                style_excel_file(output_file)
                excel_files.append(output_file)
                logger.info(f"Successfully created Excel file: {excel_filename}")
                
            except Exception as e:
                logger.error(f"خطا در ایجاد Excel برای {filename}: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
        
        return excel_files
    def create_results_section(results):
        if not results:
            return
        st.subheader("📁 نتایج تفصیلی تحلیل")
        st.divider()
        for filename, result in results:
            with st.container():
                if 'error' in result:
                    st.markdown(f'<div class="new-result-card error-card"><div class="card-header"><h5>{filename} <span class="status-icon error">✗</span></h5></div><p class="error-message">خطا در پردازش فایل: {result["error"]}</p></div>', unsafe_allow_html=True)
                    continue
                try:
                    analysis = result['تحلیل_جامع_گزارش_حسابرسی']['بخش۱_خلاصه_و_اطلاعات_کلیدی']
                    company_name = analysis.get('نام_شرکت', 'N/A')
                    auditor_name = analysis.get('نام_حسابرس', 'N/A')
                    opinion_type = analysis.get('نوع_اظهارنظر', 'N/A')
                    risk_level = analysis.get('سطح_ریسک_کلی_بنا_به_گزارش', 'N/A')
                    financial_year = analysis.get('دوره_مالی', 'N/A')
                    risk_class = get_risk_class(risk_level)
                    st.markdown(f'<div class="new-result-card"><div class="card-header"><h5>{filename} <span class="status-icon success">✓</span></h5></div><div class="new-card-grid"><div class="new-info-box"><div class="new-info-label">🏢 شرکت</div><div class="new-info-value">{company_name}</div></div><div class="new-info-box"><div class="new-info-label">📅 دوره مالی</div><div class="new-info-value">{financial_year}</div></div><div class="new-info-box"><div class="new-info-label">👨‍💼 حسابرس</div><div class="new-info-value">{auditor_name}</div></div><div class="new-info-box"><div class="new-info-label">📋 اظهارنظر</div><div class="new-info-value">{opinion_type}</div></div><div class="new-info-box new-risk-box {risk_class}"><div class="new-info-label">⚠️ سطح ریسک</div><div class="new-info-value">{risk_level}</div></div></div></div>', unsafe_allow_html=True)
                except Exception as e:
                    st.warning(f"⚠️ خطایی در نمایش نتایج فایل {filename} رخ داد: {e}")
        st.markdown("---")
        st.subheader("📥 دانلود خروجی‌ها")
        if 'show_download_options' not in st.session_state:
            st.session_state.show_download_options = False
        if 'show_individual_files' not in st.session_state:
            st.session_state.show_individual_files = False
        if st.button("📂 نمایش گزینه‌های دانلود", type="primary", key="show_downloads_main"):
            st.session_state.show_download_options = not st.session_state.show_download_options
            st.session_state.show_individual_files = False
        if st.session_state.show_download_options:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔎  دانلود فایل های اکسل", use_container_width=True, key="toggle_individual_files"):
                    st.session_state.show_individual_files = not st.session_state.show_individual_files
            with col2:
                try:
                    excel_files_zip = convert_to_excel(results)
                    if excel_files_zip:
                        zip_buffer = BytesIO()
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                            for f_path in excel_files_zip:
                                zf.write(f_path, os.path.basename(f_path))
                        zip_buffer.seek(0)
                        st.download_button(label="📦 دانلود همه فایل‌ها (ZIP)", data=zip_buffer.getvalue(), file_name=f"Financial_Analysis_All_{datetime.now().strftime('%Y%m%d')}.zip", mime="application/zip", use_container_width=True, key="download_zip_final")
                except Exception as e:
                    st.error(f"خطا در آماده‌سازی فایل ZIP: {e}")
            if st.session_state.show_individual_files:
                st.markdown("---")
                st.markdown("#### لیست فایل‌های اکسل برای دانلود:")
                try:
                    excel_files_individual = convert_to_excel(results)
                    if not excel_files_individual:
                        st.warning("هیچ فایل اکسلی برای دانلود تولید نشد.")
                    else:
                        for index, excel_file in enumerate(excel_files_individual):
                            filename = os.path.basename(excel_file)
                            with open(excel_file, 'rb') as f:
                                file_data = f.read()
                            st.download_button(label=f"📄 {filename}", data=file_data, file_name=filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"download_file_{index}", use_container_width=True)
                except Exception as e:
                    st.error(f"خطا در آماده‌سازی فایل‌های تکی: {e}")

    def create_stats_section(results):
        if not results:
            st.info("داده‌ای برای نمایش آمار وجود ندارد.")
            return
        st.markdown('<div class="modern-card">', unsafe_allow_html=True)
        st.subheader("📈 آمار تحلیل")
        st.divider()
        successful = sum(1 for _, r in results if 'error' not in r)
        failed = len(results) - successful
        risk_counts = {'پایین': 0, 'متوسط': 0, 'بالا': 0, 'بحرانی': 0}
        opinion_types = {'مقبول': 0, 'مشروط': 0, 'مردود': 0, 'عدم اظهارنظر': 0}
        company_data = []
        for filename, result in results:
            if 'error' not in result:
                try:
                    analysis = result['تحلیل_جامع_گزارش_حسابرسی']['بخش۱_خلاصه_و_اطلاعات_کلیدی']
                    risk = analysis['سطح_ریسک_کلی_بنا_به_گزارش']
                    if risk in risk_counts: 
                        risk_counts[risk] += 1
                    opinion = analysis['نوع_اظهارنظر']
                    if opinion in opinion_types:
                        opinion_types[opinion] += 1
                    company_data.append({'نام_شرکت': analysis['نام_شرکت'], 'دوره_مالی': analysis['دوره_مالی'], 'حسابرس': analysis.get('نام_حسابرس', 'نامشخص'), 'نوع_اظهارنظر': opinion, 'سطح_ریسک': risk})
                except KeyError: 
                    pass
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
                <div class="metric-modern metric-success">
                    <p>تحلیل موفق</p>
                    <div class="metric-value-box">
                        <div class="metric-value">{successful}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
                <div class="metric-modern metric-failed">
                    <p>ناموفق</p>
                    <div class="metric-value-box">
                        <div class="metric-value">{failed}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
                <div class="metric-modern metric-highrisk">
                    <p>ریسک بالا / بحرانی</p>
                    <div class="metric-value-box">
                        <div class="metric-value">{risk_counts["بالا"] + risk_counts["بحرانی"]}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
                <div class="metric-modern metric-lowrisk">
                    <p>ریسک پایین</p>
                    <div class="metric-value-box">
                        <div class="metric-value">{risk_counts["پایین"]}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        if company_data:
            # <<< بخش توزیع سطح ریسک با ساختار HTML جدید >>>
            st.markdown("<br><h3>📊 توزیع سطح ریسک</h3>", unsafe_allow_html=True)
            risk_icons = {'پایین': '🟢', 'متوسط': '🟡', 'بالا': '🟠', 'بحرانی': '🔴'}
            
            col1, col2, col3, col4 = st.columns(4)
            # ترتیب را مطابق تصویر هدف تغییر می‌دهیم (از سبز به قرمز)
            risk_types = ['پایین', 'متوسط', 'بالا', 'بحرانی']
            columns = [col1, col2, col3, col4]
            
            for col, risk_type in zip(columns, risk_types):
                with col:
                    st.markdown(f'''
                        <div class="stat-card-v2 {risk_type.lower()}">
                            <div class="card-icon-v2">{risk_icons[risk_type]}</div>
                            <div class="card-number-v2">{risk_counts[risk_type]}</div>
                            <div class="card-title-v2">ریسک {risk_type}</div>
                        </div>
                    ''', unsafe_allow_html=True)

            # <<< بخش توزیع نوع اظهارنظر با ساختار HTML جدید >>>
            st.markdown("<br><h3>📊 توزیع نوع اظهارنظر</h3>", unsafe_allow_html=True)
            opinion_icons = {'مقبول': '✅', 'مشروط': '⚠️', 'مردود': '❌', 'عدم اظهارنظر': '⭕'}
            
            col1, col2, col3, col4 = st.columns(4)
            opinion_keys = ['مقبول', 'مشروط', 'مردود', 'عدم اظهارنظر']
            columns = [col1, col2, col3, col4]
            
            for col, op_type in zip(columns, opinion_keys):
                with col:
                    st.markdown(f'''
                        <div class="stat-card-v2 {op_type.lower().replace(' ', '-')}">
                            <div class="card-icon-v2">{opinion_icons[op_type]}</div>
                            <div class="card-number-v2">{opinion_types[op_type]}</div>
                            <div class="card-title-v2">{op_type}</div>
                        </div>
                    ''', unsafe_allow_html=True)

                
            st.markdown("<br><h3>🏢 جدول خلاصه شرکت‌ها</h3>", unsafe_allow_html=True)
            html_table = '<table class="summary-table"><thead><tr><th>شرکت</th><th>دوره مالی</th><th>حسابرس</th><th>اظهارنظر</th><th>سطح ریسک</th></tr></thead><tbody>'
            for i, row in enumerate(company_data):
                risk_class = ""
                if row['سطح_ریسک'] == 'بحرانی': risk_class = "risk-critical"
                elif row['سطح_ریسک'] == 'بالا': risk_class = "risk-high"
                elif row['سطح_ریسک'] == 'متوسط': risk_class = "risk-medium"
                elif row['سطح_ریسک'] == 'پایین': risk_class = "risk-low"
                opinion_class = ""
                if row['نوع_اظهارنظر'] == 'مقبول': opinion_class = "opinion-accepted"
                elif row['نوع_اظهارنظر'] == 'مشروط': opinion_class = "opinion-conditional"
                elif row['نوع_اظهارنظر'] == 'مردود': opinion_class = "opinion-rejected"
                elif row['نوع_اظهارنظر'] == 'عدم اظهارنظر': opinion_class = "opinion-no"
                html_table += f'<tr><td>{row["نام_شرکت"]}</td><td>{row["دوره_مالی"]}</td><td>{row["حسابرس"]}</td><td class="opinion-cell {opinion_class}">{row["نوع_اظهارنظر"]}</td><td class="risk-cell {risk_class}">{row["سطح_ریسک"]}</td></tr>'
            html_table += '</tbody></table>'
            st.markdown(html_table, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


    # ========================================================================
# بخش 9: توابع UI (اصلاح نهایی برای آماده‌سازی و رسم نمودار)
# ========================================================================

    def normalize_company_name(name: str) -> str:
        """
        نرمال‌سازی نام شرکت برای تشخیص یکسان بودن بین سال‌ها
        - حذف تفاوت‌های جزئی در نام‌نویسی
        - یکسان‌سازی حروف فارسی و عربی
        - حذف کلمات و علائم اضافی
        """
        if not name:
            return ""
        
        # حذف فضاهای ابتدا و انتها
        name = name.strip()
        
        # یکسان‌سازی حروف فارسی و عربی
        name = name.replace("ي", "ی").replace("ك", "ک")
        name = name.replace("ة", "ه").replace("ؤ", "و").replace("إ", "ا").replace("أ", "ا")
        
        # تبدیل به حروف کوچک (برای زبان انگلیسی)
        name = name.lower()
        
        # حذف تمام علائم نگارشی و پرانتزها
        name = re.sub(r'[()\[\]{}،,.:;""\'`~!@#$%^&*_+=|\\/<>?]', '', name)
        
        # حذف کلمات و عبارات رایج (case-insensitive)
        patterns_to_remove = [
            r'(?i)شرکت\s*',
            r'(?i)سهامی\s*عام\s*',
            r'(?i)سهامی\s*خاص\s*',
            r'(?i)با\s*مسئولیت\s*محدود\s*',
            r'(?i)عام\s*',
            r'(?i)خاص\s*',
        ]
        
        for pattern in patterns_to_remove:
            name = re.sub(pattern, '', name)
        
        # حذف فاصله‌های اضافی و تبدیل چند فاصله به یک فاصله
        name = re.sub(r'\s+', ' ', name)
        
        # حذف فضاهای ابتدا و انتها مجدد
        name = name.strip()
        
        return name


    def process_and_prepare_dataframes(results: List) -> (Dict, bool):
        """
        این تابع نتایج JSON را مستقیماً پردازش کرده، ستون 'year' را به هر شیت اضافه می‌کند
        و داده‌ها را برای ادغام آماده می‌کند.
        """
        all_dataframes = {}
        company_names = {}  # تغییر از set به dict برای نگهداری نام اصلی و نرمال شده
        
        # 1. پردازش هر فایل به صورت مجزا
        for filename, data in results:
            if "error" in data:
                continue
                
            try:
                report = data["تحلیل_جامع_گزارش_حسابرسی"]
                summary_data = report["بخش۱_خلاصه_و_اطلاعات_کلیدی"]
                
                # استخراج سال و نام شرکت
                company_name = summary_data.get("نام_شرکت", f"Unknown_{filename}")
                normalized_name = normalize_company_name(company_name)
                
                financial_year = summary_data.get("دوره_مالی", "")
                year_match = re.search(r'(\d{4})', financial_year)
                year = int(year_match.group(1)) if year_match else None
                
                if year is None:
                    logger.warning(f"سال مالی برای فایل {filename} یافت نشد. از این فایل در نمودارها صرف‌نظر می‌شود.")
                    continue

                # ذخیره نام نرمال شده با نام اصلی
                if normalized_name not in company_names:
                    company_names[normalized_name] = company_name

                # 2. ساخت دیتافریم برای هر شیت و اضافه کردن ستون 'year'
                # شیت خلاصه
                if 'df_summary' not in all_dataframes: 
                    all_dataframes['df_summary'] = []
                df1 = pd.DataFrame([summary_data])
                df1['year'] = year
                all_dataframes['df_summary'].append(df1)
                
                # شیت تاکید بر مطالب خاص
                part2 = report.get("بخش۲_تجزیه_تحلیل_گزارش", {})
                if "بند_تاکید_بر_مطالب_خاص" in part2:
                    if 'df_emphasis' not in all_dataframes: 
                        all_dataframes['df_emphasis'] = []
                    emphasis_data = part2["بند_تاکید_بر_مطالب_خاص"]
                    if emphasis_data.get("موضوعیت_دارد", False) and "موارد_مطرح_شده" in emphasis_data:
                        df_emphasis = pd.DataFrame(emphasis_data["موارد_مطرح_شده"])
                        df_emphasis['year'] = year
                        df_emphasis['موضوعیت_دارد'] = True
                        all_dataframes['df_emphasis'].append(df_emphasis)
                    else:
                        all_dataframes['df_emphasis'].append(pd.DataFrame([{'موضوعیت_دارد': False, 'year': year}]))

                # شیت تخلفات قانونی
                if "گزارش_رعایت_الزامات_قانونی" in part2:
                    if 'df_violations' not in all_dataframes: 
                        all_dataframes['df_violations'] = []
                    legal_data = part2["گزارش_رعایت_الزامات_قانونی"]
                    if legal_data.get("موضوعیت_دارد", False) and "تخلفات" in legal_data:
                        df_legal = pd.DataFrame(legal_data["تخلفات"])
                        df_legal['year'] = year
                        df_legal['موضوعیت_دارد'] = True
                        all_dataframes['df_violations'].append(df_legal)
                    else:
                        all_dataframes['df_violations'].append(pd.DataFrame([{'موضوعیت_دارد': False, 'year': year}]))
                
                # شیت چک‌لیست
                if "بخش۳_چک_لیست_موضوعی" in report:
                    if 'df_checklist' not in all_dataframes: 
                        all_dataframes['df_checklist'] = []
                    df3 = pd.DataFrame(report["بخش۳_چک_لیست_موضوعی"])
                    df3['year'] = year
                    all_dataframes['df_checklist'].append(df3)

            except Exception as e:
                logger.error(f"خطا در آماده‌سازی دیتافریم برای فایل {filename}: {e}")
                continue

        # 3. اعتبارسنجی نام شرکت (اصلاح شده برای اجازه دادن به نام‌های متفاوت)
        if len(company_names) > 1:
            original_names = list(company_names.values())
            # به جای برگرداندن False، فقط اطلاع‌رسانی می‌کنیم
            st.info(f"ℹ️ در حال تجمیع داده‌های {len(company_names)} شرکت مختلف برای تحلیل گروهی: {', '.join(original_names)}")
            # return {}, False  <-- این خط حذف یا کامنت شد

        # 4. ادغام نهایی دیتافریم‌ها
        merged_data = {}
        for key, df_list in all_dataframes.items():
            if df_list:
                merged_data[key] = pd.concat(df_list, ignore_index=True)

        return merged_data, True


    def load_font_as_base64(font_path):
        """
        فایل فونت باینری را می‌خواند و آن را به رشته Base64 با پیشوند data URI تبدیل می‌کند.
        """
        try:
            with open(font_path, "rb") as f:  # 'rb' برای خواندن فایل به صورت باینری
                font_data = f.read()
            
            # داده باینری را به Base64 تبدیل می‌کنیم
            base64_encoded_data = base64.b64encode(font_data).decode('utf-8')
            
            # بر اساس پسوند فایل، پیشوند صحیح را تعیین می‌کنیم
            if font_path.endswith(".woff2"):
                mime_type = "font/woff2"
            elif font_path.endswith(".woff"):
                mime_type = "font/woff"
            elif font_path.endswith(".ttf"):
                mime_type = "font/truetype"
            else:
                # اگر فرمت دیگری بود، یک مقدار پیش‌فرض در نظر می‌گیریم
                mime_type = "application/font-octet-stream"

            # رشته نهایی با فرمت data URI را برمی‌گردانیم
            return f"data:{mime_type};base64,{base64_encoded_data}"

        except FileNotFoundError:
            st.error(f"خطای حیاتی: فایل فونت در مسیر '{font_path}' پیدا نشد.")
            return None
        except Exception as e:
            st.error(f"خطا در پردازش فایل فونت: {e}")
            return None

# بخش اصلاح‌شده برای نمودارها با عناوین markdown و expander توضیحات

    def create_charts_section(results):
        # 1. بررسی اولیه نتایج (این بخش بدون تغییر است)
        if not results or not any('error' not in r for _, r in results):
            st.info("داده معتبری برای نمایش نمودارها وجود ندارد.")
            return

        st.markdown('<div class="modern-card">', unsafe_allow_html=True)
        st.subheader("📈 نمودارها و تحلیل روند")

        # ==================== بخش کلیدی: خواندن فونت از فایل ====================
        # ✅ تمام این منطق باید داخل تابع باشد
        
        # 2. فونت را از فایل متنی جداگانه بارگذاری می‌کنیم
        font_base64_string = load_font_as_base64("fonts/BMITRA.woff2")

        # 3. بررسی می‌کنیم که آیا فونت با موفقیت بارگذاری شده است یا خیر
        # اگر فایل فونت پیدا نشد، یک پیام هشدار نمایش داده و اجرای این تابع را متوقف می‌کنیم
        if not font_base64_string:
            st.warning("فایل فونت بارگذاری نشد، در نتیجه فهرست گرافیکی نمودارها نمایش داده نمی‌شود.")
            # این 'return' متعلق به تابع create_charts_section است و باعث خروج از آن می‌شود
            st.markdown("</div>", unsafe_allow_html=True)
            return

        # 4. اگر فونت با موفقیت بارگذاری شد، ادامه می‌دهیم و کامپوننت HTML را می‌سازیم
        #تنظیم فونت برای فهرست نمودارها
        html_with_embedded_font = f"""
        <!DOCTYPE html>
        <html lang="fa" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <style>
                @font-face {{
                    font-family: 'B Mitra';
                    src: url('{font_base64_string}') format('woff2');
                    font-weight: normal;
                    font-style: normal;
                }}
                * {{
                    font-family: 'B Mitra','Noto Naskh Arabic', Tahoma, Arial, sans-serif !important;
                }}
            </style>
        </head>
        <body>
            <div style="background: #f0f4f8; padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem; direction: rtl;">
                <h2 style="text-align: center; color: #2c3e50; margin-bottom: 1.5rem; margin-top: 0; font-size: 1.7rem;">📊 فهرست نمودارها</h2>
                <div style="background: white; padding: 1.2rem; border-radius: 10px; margin-bottom: 1rem; border-right: 5px solid #667eea; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <h3 style="color: #4c51bf; margin: 0 0 0.5rem 0; font-size: 1.4rem;">📊 بخش ۱: تحلیل روندهای کلان حسابرسی</h3>
                </div>
                <div style="background: white; padding: 1.2rem; border-radius: 10px; margin-bottom: 1rem; border-right: 5px solid #f97316; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <h3 style="color: #4c51bf; margin: 0 0 0.5rem 0; font-size: 1.4rem;">⚠️ بخش ۲: تحلیل ریسک‌های برجسته شده در گزارش</h3>
                </div>
                <div style="background: white; padding: 1.2rem; border-radius: 10px; margin-bottom: 1rem; border-right: 5px solid #f59e0b; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <h3 style="color: #4c51bf; margin: 0 0 0.5rem 0; font-size: 1.4rem;">⚖️ بخش ۳: تحلیل تخلفات و الزامات قانونی</h3>
                </div>
                <div style="background: white; padding: 1.2rem; border-radius: 10px; border-right: 5px solid #ef4444; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <h3 style="color: #4c51bf; margin: 0 0 0.5rem 0; font-size: 1.4rem;">🔥 بخش ۴: نقشه حرارتی موضوعات کلیدی حسابرسی</h3>
                </div>
                <div style="margin-top: 1.5rem; padding: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; text-align: center;">
                    <p style="color: white; margin: 0; font-size: 1.4rem; font-weight: bold;">📈 مجموع: 7 نمودار تحلیلی در 4 بخش </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        components.html(html_with_embedded_font, height=600)
                
        # st.divider()

        try:
            font = setup_persian_font()
            
            # آماده‌سازی و ادغام داده‌ها
            merged_data, is_consistent = process_and_prepare_dataframes(results)
            
            if not is_consistent or not merged_data:
                st.markdown("</div>", unsafe_allow_html=True)
                return

            df_summary = merged_data.get("df_summary")
            df_emphasis = merged_data.get("df_emphasis")
            df_checklist = merged_data.get("df_checklist")
            df_violations = merged_data.get("df_violations")

            # ====================================================================
            # بخش ۱: روندهای کلان
            # ====================================================================
            st.markdown('''
                <h2 style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 2rem; 
                        border-radius: 20px; 
                        margin: 2.5rem 0; 
                        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
                        color: white; 
                        text-align: center; 
                        font-size: 1.8rem; 
                        font-weight: 700; 
                        letter-spacing: 1px;">
                    📊 بخش ۱: تحلیل روندهای کلان حسابرسی
                </h2>
                ''', unsafe_allow_html=True)
       
            
            col1, col2 = st.columns(2, gap="large")
            
            # نمودار ۱: روند سطح ریسک
            with col1:
                if df_summary is not None and not df_summary.empty:
                    st.markdown('''
                        <h3 style="background: rgba(240, 147, 251, 0.3); 
                                padding: 0.8rem 1.5rem; 
                                border-radius: 12px; 
                                margin: 0.5rem 0 0 0;
                                color: #2c3e50; 
                                text-align: center; 
                                font-size: 1.2rem; 
                                font-weight: 600;">
                            ⚠️ روند سطح ریسک کلی
                        </h3>
                    ''', unsafe_allow_html=True)
                    
                    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                    fig1 = plot_risk_trend(df_summary, font)
                    st.pyplot(fig1)
                    plt.close(fig1)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    with st.expander("📖 توضیحات نمودار روند ریسک"):
                        st.markdown("""
                        <div style="text-align: right; direction: rtl; padding: 1rem;">
                        
                        **این نمودار چه چیزی را نشان می‌دهد؟**
                        
                        - **محور عمودی**: سطح ریسک (پایین، متوسط، بالا، بحرانی)
                        - **محور افقی**: سال‌های مالی مورد بررسی
                        - **خط روند**: تغییرات سطح ریسک کلی در طول زمان
                        
                        **نکات کلیدی:**
                        - افزایش روند به سمت بالا نشان‌دهنده افزایش ریسک است
                        - کاهش روند نشان‌دهنده بهبود وضعیت کنترل‌های داخلی و کاهش ریسک
                        - ثبات در یک سطح نشان‌دهنده وضعیت پایدار سازمان است
                        
                        </div>
                        """, unsafe_allow_html=True)
            
            # نمودار ۲: روند اظهارنظر
            with col2:
                if df_summary is not None and not df_summary.empty:
                    st.markdown('''
                        <h3 style="background: rgba(250, 112, 154, 0.3); 
                                padding: 0.8rem 1.5rem; 
                                border-radius: 12px; 
                                margin: 0.5rem 0 0 0;
                                color: #2c3e50; 
                                text-align: center; 
                                font-size: 1.2rem; 
                                font-weight: 600;">
                            ✅ روند اظهارنظر حسابرس
                        </h3>
                    ''', unsafe_allow_html=True)
                    
                    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                    fig2 = plot_opinion_trend(df_summary, font)
                    st.pyplot(fig2)
                    plt.close(fig2)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    with st.expander("📖 توضیحات نمودار روند اظهارنظر"):
                        st.markdown("""
                        <div style="text-align: right; direction: rtl; padding: 1rem;">
                        
                        **این نمودار چه چیزی را نشان می‌دهد؟**
                        
                        - **محور عمودی**: نوع اظهارنظر (مقبول، مشروط، مردود، عدم اظهارنظر)
                        - **محور افقی**: سال‌های مالی
                        - **خط روند**: تغییرات نوع نظر حسابرس در طول زمان
                        
                        **تفسیر:**
                        - **مقبول**: صورت‌های مالی عاری از تحریف با اهمیت
                        - **مشروط**: وجود محدودیت یا انحراف قابل توجه
                        - **مردود**: عدم انطباق با استانداردها
                        - **عدم اظهارنظر**: عدم امکان رسیدگی کافی
                        
                        </div>
                        """, unsafe_allow_html=True)

 

            # ====================================================================
            # بخش ۳: ریسک‌های برجسته
            # ====================================================================
            st.markdown('''
                <h2 style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); 
                        padding: 2rem; 
                        border-radius: 20px; 
                        margin: 2.5rem 0; 
                        box-shadow: 0 10px 30px rgba(79, 172, 254, 0.3);
                        color: white; 
                        text-align: center; 
                        font-size: 1.8rem; 
                        font-weight: 700; 
                        letter-spacing: 1px;">
                    ⚠️ بخش ۲: تحلیل ریسک‌های برجسته شده در گزارش
                </h2>
            ''', unsafe_allow_html=True)
            
            if df_emphasis is not None and not df_emphasis.empty and df_emphasis['موضوعیت_دارد'].any():
                col3, col4 = st.columns([1, 1], gap="large")
                
                # نمودار ۴: ستونی انباشته ریسک‌ها
                with col3:
                    st.markdown('''
                        <h3 style="background: rgba(255, 183, 197, 0.3); 
                                padding: 0.8rem 1.5rem; 
                                border-radius: 12px; 
                                margin: 0.5rem 0 0 0;
                                color: #2c3e50; 
                                text-align: center; 
                                font-size: 1.2rem; 
                                font-weight: 600;">
                            📊 روند تعداد و ترکیب ریسک‌ها
                        </h3>
                    ''', unsafe_allow_html=True)
                    
                    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                    fig4 = plot_risk_stacked_bar(df_emphasis, font)
                    st.pyplot(fig4)
                    plt.close(fig4)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    with st.expander("📖 توضیحات نمودار ستونی ریسک‌ها"):
                        st.markdown("""
                        <div style="text-align: right; direction: rtl; padding: 1rem;">
                        
                        **این نمودار چه چیزی را نشان می‌دهد؟**
                        
                        - **ستون‌ها**: تعداد کل ریسک‌های برجسته شده در هر سال
                        - **رنگ‌های مختلف**: دسته‌های اصلی ریسک (اعتباری، بازار، عملیاتی و...)
                        - **عدد روی هر بخش**: تعداد موارد آن دسته ریسک
                        
                        **تحلیل:**
                        - افزایش ارتفاع ستون = افزایش تعداد کل ریسک‌ها
                        - تغییر ترکیب رنگ‌ها = تغییر در نوع ریسک‌های غالب
                        - غلبه یک رنگ = تمرکز ریسک در یک دسته خاص
                        
                        **هشدار:** افزایش ناگهانی در یک دسته ریسک خاص نیاز به توجه ویژه دارد.
                        
                        </div>
                        """, unsafe_allow_html=True)
                
                # نمودار ۵: Sunburst ریسک‌ها
                with col4:
                    st.markdown('''
                        <h3 style="background: rgba(210, 153, 194, 0.3); 
                                padding: 0.8rem 1.5rem; 
                                border-radius: 12px; 
                                margin: 0.5rem 0 0 0;
                                color: #2c3e50; 
                                text-align: center; 
                                font-size: 1.2rem; 
                                font-weight: 600;">
                            🎯 توزیع سلسله‌مراتبی ریسک‌ها
                        </h3>
                    ''', unsafe_allow_html=True)
                    
                    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                    fig5 = plot_risk_sunburst(df_emphasis)
                    st.plotly_chart(fig5, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    with st.expander("📖 توضیحات نمودار سلسله مراتبی ریسک‌ها"):
                        st.markdown("""
                        <div style="text-align: right; direction: rtl; padding: 1rem;">
                        
                        **این نمودار چه چیزی را نشان می‌دهد؟**
                        
                        - **مرکز دایره**: کل ریسک‌های برجسته شده
                        - **حلقه داخلی**: دسته‌های اصلی ریسک
                        - **حلقه خارجی**: زیرشاخه‌های هر دسته اصلی
                        
                        **نحوه استفاده:**
                        - اندازه هر قطاع متناسب با تعداد موارد آن است
                        - کلیک روی هر قسمت برای بزرگ‌نمایی
                        - Hover برای مشاهده جزئیات (نام، تعداد، درصد)
                        
                        **مزایا:**
                        - دید کلی از توزیع ریسک‌ها در یک نگاه
                        - شناسایی سریع پرتکرارترین دسته‌های ریسک
                        - درک رابطه بین دسته اصلی و زیرشاخه‌ها
                        
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("📌 ریسک برجسته‌ای در این گزارش‌ها ذکر نشده است.")

            # ====================================================================
            # بخش ۴: تخلفات قانونی
            # ====================================================================
            st.markdown('''
                <h2 style="background: linear-gradient(135deg, #30cfd0 0%, #330867 100%); 
                        padding: 2rem; 
                        border-radius: 20px; 
                        margin: 2.5rem 0; 
                        box-shadow: 0 10px 30px rgba(48, 207, 208, 0.3);
                        color: white; 
                        text-align: center; 
                        font-size: 1.8rem; 
                        font-weight: 700; 
                        letter-spacing: 1px;">
                    ⚖️ بخش ۳: تحلیل تخلفات و الزامات قانونی
                </h2>
            ''', unsafe_allow_html=True)
            
            if df_violations is not None and not df_violations.empty and df_violations['موضوعیت_دارد'].any():
                col5, col6 = st.columns([1, 1], gap="large")
                
                # نمودار ۶: ستونی انباشته تخلفات
                with col5:
                    st.markdown('''
                        <h3 style="background: rgba(252, 74, 26, 0.3); 
                                padding: 0.8rem 1.5rem; 
                                border-radius: 12px; 
                                margin: 0.5rem 0 0 0;
                                color: #2c3e50; 
                                text-align: center; 
                                font-size: 1.2rem; 
                                font-weight: 600;">
                            📉 روند تعداد و ترکیب تخلفات
                        </h3>
                    ''', unsafe_allow_html=True)
                    
                    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                    fig6 = plot_violations_stacked_bar(df_violations, font)
                    st.pyplot(fig6)
                    plt.close(fig6)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    with st.expander("📖 توضیحات نمودار تخلفات قانونی"):
                        st.markdown("""
                        <div style="text-align: right; direction: rtl; padding: 1rem;">
                                
                        **این نمودار چه چیزی را نشان می‌دهد؟**
                        
                        - **ستون‌ها**: تعداد کل موارد عدم رعایت الزامات قانونی
                        - **رنگ‌ها**: دسته‌بندی تخلفات (نهاد ناظر، بازار سرمایه، حاکمیتی، مالیاتی و...)
                        - **اعداد**: تعداد موارد تخلف در هر دسته
                        
                        **اهمیت:**
                        - افزایش تخلفات = ضعف در رعایت الزامات قانونی
                        - کاهش تخلفات = بهبود سیستم‌های کنترلی و حاکمیتی
                        - تکرار تخلف در یک دسته = نیاز به اقدام اصلاحی اساسی
                        
                        **توجه:** تخلفات قانونی می‌تواند منجر به جریمه‌های مالی و آسیب به شهرت سازمان شود.
                                    
                        </div>
                        """,unsafe_allow_html=True)
                
                # نمودار ۷: Sunburst تخلفات
                with col6:
                    st.markdown('''
                        <h3 style="background: rgba(238, 156, 167, 0.3); 
                                padding: 0.8rem 1.5rem; 
                                border-radius: 12px; 
                                margin: 0.5rem 0 0 0;
                                color: #2c3e50; 
                                text-align: center; 
                                font-size: 1.2rem; 
                                font-weight: 600;">
                            🔍 ساختار و توزیع تخلفات
                        </h3>
                    ''', unsafe_allow_html=True)
                    
                    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                    fig7 = plot_violations_sunburst(df_violations)
                    st.plotly_chart(fig7, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    with st.expander("📖 توضیحات نمودار سلسله مراتبی تخلفات"):
                        st.markdown("""
                            <div style="text-align: right; direction: rtl; padding: 1rem;">
                                    
                        **این نمودار چه چیزی را نشان می‌دهد؟**
                        
                        - **حلقه مرکزی**: کل تخلفات
                        - **حلقه میانی**: دسته‌های اصلی قوانین (الزامات بانک مرکزی، بورس، حاکمیتی و...)
                        - **حلقه خارجی**: جزئیات تخلف در هر دسته
                        
                        **کاربردها:**
                        - شناسایی پرتکرارترین نوع تخلف
                        - درک رابطه بین دسته اصلی قانون و موارد تخلف
                        - اولویت‌بندی برای اقدامات اصلاحی
                        
                        **نکته مهم:** 
                        تمرکز تخلفات در یک دسته خاص (مثلاً الزامات بانک مرکزی) 
                        نشان‌دهنده نیاز به توجه ویژه به آن حوزه است.
                                    
                        </div>
                        """,unsafe_allow_html=True)
            else:
                st.info("✅ در این گزارش‌ها، تخلف قانونی گزارش نشده است.")


           # ====================================================================
            # بخش 4: نقشه حرارتی
            # ====================================================================
            st.markdown('''
                <h2 style="background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); 
                        padding: 2rem; 
                        border-radius: 20px; 
                        margin: 2.5rem 0; 
                        box-shadow: 0 10px 30px rgba(168, 237, 234, 0.3);
                        color: #2c3e50; 
                        text-align: center; 
                        font-size: 1.8rem; 
                        font-weight: 700; 
                        letter-spacing: 1px;">
                    🔥 بخش ۴: نقشه حرارتی موضوعات کلیدی حسابرسی
                </h2>
            ''', unsafe_allow_html=True)
            
            if df_checklist is not None and not df_checklist.empty:
                st.markdown('''
                    <h3 style="background: rgba(255, 154, 158, 0.3); 
                            padding: 0.8rem 1.5rem; 
                            border-radius: 12px; 
                            margin: 0.5rem 0 0 0;
                            color: #2c3e50; 
                            text-align: center; 
                            font-size: 1.2rem; 
                            font-weight: 600;">
                        🎯 نقشه حرارتی وضعیت موضوعات کلیدی
                    </h3>
                ''', unsafe_allow_html=True)
                
                st.markdown('<div class="chart-container-full">', unsafe_allow_html=True)
                fig3 = plot_checklist_heatmap(df_checklist, font)
                st.pyplot(fig3)
                plt.close(fig3)
                st.markdown('</div>', unsafe_allow_html=True)
                
                with st.expander("📖 توضیحات نقشه حرارتی"):
                    st.markdown("""
                    <div style="text-align: right; direction: rtl; padding: 1rem;">
                    
                    **این نقشه چه چیزی را نشان می‌دهد؟**
                    
                    - **ردیف‌ها**: موضوعات کلیدی مورد بررسی (کفایت سرمایه، تسعیر ارز، مالیات و...)
                    - **ستون‌ها**: سال‌های مالی
                    - **رنگ سلول‌ها**: سطح ریسک یا وضعیت هر موضوع
        
                    **کاربرد:**
                    - شناسایی موضوعات تکراری در طول زمان
                    - تشخیص روند بهبود یا بدتر شدن هر موضوع
                    - اولویت‌بندی موضوعات پرریسک
                    
                    </div>
                    """, unsafe_allow_html=True)
                
        except Exception as e:
            st.error(f"❌ خطا در رسم نمودارها: {str(e)}")
            logger.error(f"Chart error: {traceback.format_exc()}")
            
        st.markdown("</div>", unsafe_allow_html=True)

    def normalize_company_name(name: str) -> str:
        """
        نرمال‌سازی خیلی ضعیف: فقط برای جلوگیری از خطاهای تایپی
        بیشتر نام‌ها متفاوت باقی می‌مانند تا کاربر خودش تصمیم بگیرد
        """
        if not name:
            return ""
        
        # فقط حذف فضاهای اضافی و یکسان‌سازی حروف عربی/فارسی
        name = name.strip()
        name = name.replace("ي", "ی").replace("ك", "ک")
        name = name.replace("ة", "ه").replace("ؤ", "و").replace("إ", "ا").replace("أ", "ا")
        name = re.sub(r'\s+', ' ', name)
        
        return name


    def analyze_companies(results: List) -> Dict:
        """
        تحلیل و شناسایی شرکت‌های موجود در نتایج
        بدون ادغام خودکار - کاربر باید خودش تصمیم بگیرد
        """
        companies_info = {}
        
        for filename, data in results:
            if "error" in data:
                continue
                
            try:
                report = data["تحلیل_جامع_گزارش_حسابرسی"]
                summary = report["بخش۱_خلاصه_و_اطلاعات_کلیدی"]
                
                company_name = summary.get("نام_شرکت", f"Unknown_{filename}")
                normalized = normalize_company_name(company_name)
                
                # استخراج سال
                financial_year = summary.get("دوره_مالی", "")
                year_match = re.search(r'(\d{4})', financial_year)
                year = int(year_match.group(1)) if year_match else None
                
                # ذخیره اطلاعات
                if normalized not in companies_info:
                    companies_info[normalized] = {
                        'original_name': company_name,
                        'normalized_name': normalized,
                        'files': [],
                        'years': [],
                        'risk_levels': [],
                        'opinion_types': []
                    }
                
                companies_info[normalized]['files'].append(filename)
                if year:
                    companies_info[normalized]['years'].append(year)
                companies_info[normalized]['risk_levels'].append(
                    summary.get("سطح_ریسک_کلی_بنا_به_گزارش", "نامشخص")
                )
                companies_info[normalized]['opinion_types'].append(
                    summary.get("نوع_اظهارنظر", "نامشخص")
                )
                
            except Exception as e:
                logger.error(f"خطا در تحلیل {filename}: {e}")
                continue
        
        # مرتب‌سازی سال‌ها
        for info in companies_info.values():
            info['years'] = sorted(info['years'])
            info['year_range'] = f"{min(info['years'])} - {max(info['years'])}" if info['years'] else "نامشخص"
            info['file_count'] = len(info['files'])
        
        return {
            'companies': companies_info,
            'total_companies': len(companies_info),
            'is_single_company': len(companies_info) == 1,
            'company_names': [info['original_name'] for info in companies_info.values()]
        }


    def create_company_merger_interface(analysis: Dict) -> Dict[str, List[str]]:
        """
        رابط کاربری برای ادغام دستی شرکت‌ها
        """
        st.subheader("شرکت‌های شناسایی شده")
        
        # مقداردهی session state
        if 'company_mergers' not in st.session_state:
            st.session_state.company_mergers = {}
        
        companies = list(analysis['companies'].keys())
        
        if len(companies) < 2:
            st.info("📌 فقط یک شرکت شناسایی شده است.")
            return {}
        
        
        
        # نمایش فشرده لیست شرکت‌ها
        for normalized_name, info in sorted(
            analysis['companies'].items(), 
            key=lambda x: x[1]['file_count'], 
            reverse=True
        ):
            st.markdown(f"""
                <div style="background: white; 
                            padding: 0.8rem; 
                            border-radius: 8px; 
                            border-right: 3px solid #2196f3;
                            margin-bottom: 0.5rem;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <span style="font-weight: bold; color: #2c3e50;">
                        {info['original_name']}
                    </span>
                    <span style="background: #e3f2fd; 
                                padding: 0.2rem 0.5rem; 
                                border-radius: 10px; 
                                font-size: 0.8rem;
                                margin-right: 0.5rem;">
                        📅 {info['year_range']}
                    </span>
                    <span style="background: #f3e5f5; 
                                padding: 0.2rem 0.5rem; 
                                border-radius: 10px; 
                                font-size: 0.8rem;">
                        📊 {info['file_count']} سال
                    </span>
                </div>
            """, unsafe_allow_html=True)
        
        # فرم ایجاد گروه جدید
        st.markdown("### ➕ ایجاد گروه ادغام جدید برای شرکت‌های یکسان")
        with st.expander("ℹ️ راهنما: چگونه شرکت‌ها را ادغام کنیم؟", expanded=False):
            st.markdown("""
            <div style="text-align: right; direction: rtl; padding: 1rem; border-radius: 8px;">
            
            **📌 هدف از ادغام:**
            
            اگر صورت‌های مالی یک شرکت با نام‌های مختلف شناسایی شده‌اند، می‌توانید آن‌ها را در یک گروه قرار دهید.
            
            **مثال‌های نیاز به ادغام:**
            
            ✅ **تغییر جزئی نام:**
            - "بانک ملت" و "بانک ملت (سهامی عام)"
            - "صنایع پتروشیمی خلیج فارس" و "شرکت صنایع پتروشیمی خلیج فارس"
            
            ✅ **تغییر نام تجاری:**
            - "پارس خودرو" → "ایران خودرو"
            - "گروه صنعتی ایران" → "هلدینگ صنعتی ایران"
            
            ✅ **ادغام یا تغییر نام قانونی:**
            - "بانک اقتصاد نوین" + "موسسه اعتباری نوین"
            
            ---
            
            **🔧 نحوه استفاده:**
            
            1. از لیست پایین، یک شرکت را به عنوان **"نام اصلی"** انتخاب کنید
            2. سایر شرکت‌هایی که باید ادغام شوند را انتخاب کنید
            3. روی دکمه **"ثبت گروه"** کلیک کنید
            4. برای رسم نمودار، فقط نام اصلی را انتخاب کنید
            
            </div>
            """, unsafe_allow_html=True)


        col1, col2 = st.columns(2)
        
        with col1:
            main_company = st.selectbox(
                "نام اصلی شرکت (مرجع):",
                options=companies,
                format_func=lambda x: f"{analysis['companies'][x]['original_name']} ({analysis['companies'][x]['file_count']} سال)",
                key="main_company_select"
            )
        
        with col2:
            # فیلتر شرکت‌هایی که قبلاً در گروه نیستند
            available_companies = [
                c for c in companies 
                if c not in st.session_state.company_mergers.keys() and c != main_company
            ]
            
            related_companies = st.multiselect(
                "شرکت‌های مرتبط (همان شرکت با نام دیگر):",
                options=available_companies,
                format_func=lambda x: f"{analysis['companies'][x]['original_name']} ({analysis['companies'][x]['file_count']} سال)",
                key="related_companies_select"
            )
        
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        
        with col_btn1:
            if st.button("✅ ثبت گروه", type="primary", use_container_width=True):
                if main_company:
                    st.session_state.company_mergers[main_company] = [main_company] + related_companies
                    
                    total_files = sum([
                        analysis['companies'][c]['file_count'] 
                        for c in [main_company] + related_companies
                    ])
                    # st.success(f"✅ گروه ثبت شد: {analysis['companies'][main_company]['original_name']} (مجموع {total_files} فایل)")
                    st.rerun()
        
        with col_btn2:
            if st.button("🔄 پاک کردن همه", use_container_width=True):
                st.session_state.company_mergers = {}
                st.rerun()
                
        # --- جابجایی محل نمایش: لیست گروه‌های ادغام شده اینجا نمایش داده می‌شود ---
        if st.session_state.company_mergers:
            # st.markdown("### 📌 گروه‌های ادغام شده:")
            
            for main_name, merged_list in st.session_state.company_mergers.items():
                main_original = analysis['companies'][main_name]['original_name']
                merged_originals = [
                    analysis['companies'][n]['original_name'] 
                    for n in merged_list if n != main_name
                ]
                
                total_files = sum([
                    analysis['companies'][n]['file_count'] 
                    for n in merged_list
                ])
                
                # col_res1, col_res2 = st.columns([5, 1])
                # with col_res1:
                st.markdown(f"""
                    <div style="background: #e8f5e9; 
                                padding: 1rem; 
                                border-radius: 10px; 
                                margin-bottom: 0.5rem;
                                border-right: 5px solid #4caf50;">
                        <strong>🏢 نام اصلی:</strong> {main_original} 
                        <span style="background: #4caf50; color: white; padding: 0.2rem 0.6rem; 
                                    border-radius: 12px; font-size: 0.85rem; margin-right: 0.5rem;">
                            {total_files} فایل
                        </span>
                        <br>
                        {'<strong>🔗 شامل:</strong> ' + ', '.join(merged_originals) if merged_originals else ''}
                    </div>
                """, unsafe_allow_html=True)
                
                # with col_res2:
                #     if st.button("🗑️", key=f"delete_{main_name}", use_container_width=True):
                #         del st.session_state.company_mergers[main_name]
                #         st.rerun()
        
        return st.session_state.company_mergers


    def apply_company_mergers(results: List, mergers: Dict[str, List[str]]) -> Dict[str, List]:
        """
        اعمال ادغام‌های شرکت روی نتایج
        """
        
        if not mergers:
            return {}
        
        # ایجاد نگاشت معکوس
        reverse_map = {}
        for main_name, merged_list in mergers.items():
            for name in merged_list:
                reverse_map[name] = main_name
        
        # گروه‌بندی نتایج
        grouped_results = {main_name: [] for main_name in mergers.keys()}
        
        for filename, data in results:
            if "error" in data:
                continue
            
            try:
                report = data["تحلیل_جامع_گزارش_حسابرسی"]
                summary = report["بخش۱_خلاصه_و_اطلاعات_کلیدی"]
                company_name = summary.get("نام_شرکت", "")
                normalized = normalize_company_name(company_name)
                
                if normalized in reverse_map:
                    main_group = reverse_map[normalized]
                    grouped_results[main_group].append((filename, data))
            
            except Exception as e:
                logger.error(f"خطا در گروه‌بندی {filename}: {e}")
                continue
        
        return grouped_results



    def create_company_selector_with_merger(results: List) -> Tuple[str, Dict, List]:
        """
        رابط کاربری برای انتخاب شرکت با قابلیت ادغام
        """
        # تحلیل شرکت‌ها
        analysis = analyze_companies(results)
        
        # رابط ادغام شرکت‌ها
        mergers = create_company_merger_interface(analysis)
        
        # st.markdown("---")
        
        # اعمال ادغام‌ها
        if mergers:
            # نتایج ادغام شده
            grouped_results = apply_company_mergers(results, mergers)
            
            # 1) نام‌های شرکت اصلی از گروه‌های ادغام شده
            merged_main_names = list(mergers.keys())
            
            # 2) شرکت‌هایی که در هیچ گروه ادغامی نیستند (مستقل)
            merged_members = set()
            for main, members in mergers.items():
                for m in members:
                    merged_members.add(m)
            
            all_company_keys = list(analysis['companies'].keys())
            independent_companies = [c for c in all_company_keys if c not in merged_members]
            
            # 3) لیست نهایی: گروه‌های ادغامی + شرکت‌های مستقل
            available_companies = []
            seen = set()
            
            for c in merged_main_names + independent_companies:
                if c not in seen:
                    available_companies.append(c)
                    seen.add(c)
            
            # تابع کمکی برای نمایش تعداد فایل
            def file_count(x):
                if x in grouped_results:
                    return len(grouped_results[x])
                return analysis['companies'][x]['file_count']
            
            def company_label(x):
                if x in mergers:
                    return f"🔗 {analysis['companies'][x]['original_name']} (گروه ادغام - {file_count(x)} فایل)"
                else:
                    return f"{analysis['companies'][x]['original_name']} ({file_count(x)} فایل)"
            
            st.subheader("🏢انتخاب شرکت برای رسم نمودار")
            
            # if len(available_companies) > 1:
            #     st.info(f"📊 تعداد شرکت‌های قابل انتخاب: {len(available_companies)} ({len(merged_main_names)} گروه ادغامی + {len(independent_companies)} مستقل)")
            
            selected_company = st.selectbox(
                "شرکت مورد نظر برای رسم نمودار:",
                options=available_companies,
                format_func=company_label,
                key="selected_company_for_chart"
            )
            
            if selected_company:
                # اگر گروه ادغامی است
                if selected_company in grouped_results:
                    # --- تغییر: نمایش جزئیات گروه ادغامی در اینجا حذف شد ---
                    return selected_company, analysis, grouped_results[selected_company]
                
                # شرکت مستقل است
                else:
                    company_results = []
                    for filename, data in results:
                        if "error" not in data:
                            try:
                                report = data["تحلیل_جامع_گزارش_حسابرسی"]
                                summary = report["بخش۱_خلاصه_و_اطلاعات_کلیدی"]
                                comp_name = summary.get("نام_شرکت", "")
                                
                                if normalize_company_name(comp_name) == selected_company:
                                    company_results.append((filename, data))
                            except:
                                continue
                    
                    # --- تغییر: نمایش جزئیات شرکت مستقل در اینجا حذف شد ---
                    return selected_company, analysis, company_results
        
        else:
            # حالت بدون ادغام - نمایش همه شرکت‌ها
            st.subheader("🏢 انتخاب شرکت برای رسم نمودار")

            
            if analysis['is_single_company']:
                company_name = list(analysis['companies'].keys())[0]
                st.success(f"✅ فقط یک شرکت شناسایی شده: {analysis['companies'][company_name]['original_name']}")
                
                # فیلتر نتایج
                company_results = []
                for filename, data in results:
                    if "error" not in data:
                        try:
                            report = data["تحلیل_جامع_گزارش_حسابرسی"]
                            summary = report["بخش۱_خلاصه_و_اطلاعات_کلیدی"]
                            comp_name = summary.get("نام_شرکت", "")
                            
                            if normalize_company_name(comp_name) == company_name:
                                company_results.append((filename, data))
                        except:
                            continue
                
                return company_name, analysis, company_results
            
            else:
                companies = list(analysis['companies'].keys())
                
                selected_company = st.selectbox(
                    "یک شرکت برای رسم نمودار انتخاب کنید:",
                    options=companies,
                    format_func=lambda x: f"{analysis['companies'][x]['original_name']} ({analysis['companies'][x]['file_count']} فایل)",
                    key="selected_single_company"
                )
                
                if selected_company:
                    company_results = []
                    for filename, data in results:
                        if "error" not in data:
                            try:
                                report = data["تحلیل_جامع_گزارش_حسابرسی"]
                                summary = report["بخش۱_خلاصه_و_اطلاعات_کلیدی"]
                                comp_name = summary.get("نام_شرکت", "")
                                
                                if normalize_company_name(comp_name) == selected_company:
                                    company_results.append((filename, data))
                            except:
                                continue
                    
                    return selected_company, analysis, company_results
                
                return None, analysis, []


    def create_filtered_charts_section(results: List):
        """
        بخش نمودارها با قابلیت ادغام و انتخاب شرکت
        """
        
        if not results or not any('error' not in r for _, r in results):
            st.info("داده معتبری برای نمایش نمودارها وجود ندارد.")
            return
        
        # گام 1: انتخاب شرکت با قابلیت ادغام
        selected_company, analysis, company_results = create_company_selector_with_merger(results)
        
        if not selected_company or not company_results:
            st.warning("⚠️ لطفاً یک شرکت انتخاب کنید تا نمودارها رسم شوند.")
            return
        
        # بررسی تعداد داده‌ها
        # if len(company_results) < 2:
        #     st.error(f"❌ برای رسم نمودار روند، حداقل 2 سال داده نیاز است. تعداد فعلی: {len(company_results)}")
        #     return
        
        # گام 2: رسم نمودارها
        # st.markdown("---")
        st.success(f"✅ در حال رسم نمودارها برای: **{analysis['companies'][selected_company]['original_name']}** ({len(company_results)} فایل)")
        
        try:
            # فراخوانی تابع اصلی رسم نمودار
            create_charts_section(company_results)
            
        except Exception as e:
            st.error(f"❌ خطا در رسم نمودارها: {str(e)}")
            logger.error(f"Chart error: {traceback.format_exc()}")
    def main():
        # مقداردهی اولیه session_state در ابتدای برنامه
        if 'results' not in st.session_state:
            st.session_state.results = None
        if 'processing_active' not in st.session_state:
            st.session_state.processing_active = False

        create_header()
        tab1, tab2, tab3, tab4 = st.tabs(["📤 آپلود و پردازش", "📊نتایج تحلیل", "📈 اطلاعات آماری", "📉 ترند و نمودارها"])
        
        with tab1:
            with st.expander("📋 راهنمای بارگذاری فایل", expanded=False):
                st.markdown("""
                <div style="text-align: right; direction: rtl; padding: 1rem; border-radius: 12px;">
                
                #### ✨ مراحل کار:
                
                * 📄 **فایل‌های PDF گزارش حسابرسی** را انتخاب کنید
                * 📦 یا یک **فایل ZIP** حاوی چندین PDF بارگذاری کنید
                * ✅ پس از انتخاب، فایل‌ها را بررسی کنید
                * 🚀 دکمه **"شروع تحلیل"** را بزنید تا پردازش آغاز شود
                
                ---
                
                #### ⚠️ نکات مهم:
                
                * **فرمت پشتیبانی شده:** فقط PDF
                * **حداکثر حجم هر فایل:** 50 مگابایت
                * **کیفیت مهم است:** اسکن‌های واضح نتایج بهتری دارند
                
                ---
                
                #### 🎯 ویژگی‌های بررسی شده:
                
                ✔️ **اطلاعات شرکت** - نام، دوره مالی  
                ✔️ **اظهارنظر حسابرس** - نوع و سطح ریسک  
                ✔️ **ریسک‌های برجسته** - تشخیص و دسته‌بندی  
                ✔️ **تخلفات قانونی** - شناسایی، تحلیل و دسته بندی  
                ✔️ **موضوعات کلیدی** - شناسایی و تحلیل  
                            
                </div>
                """, unsafe_allow_html=True)

            uploaded_files = create_file_upload_section()
            if uploaded_files:
                create_processing_section(uploaded_files)

        with tab2:
            if st.session_state.results:
                create_results_section(st.session_state.results)
            else:
                st.info("هنوز فایلی پردازش نشده است.")
        
        with tab3:
            if st.session_state.results:
                create_stats_section(st.session_state.results)
            else:
                st.info("هنوز فایلی پردازش نشده است.")
        
        with tab4:
            with st.expander("📉 راهنمای نمودارها و ترند", expanded=False):
                st.markdown("""
                    <div style="text-align: right; direction: rtl; padding: 1rem; border-radius: 12px;">

                    #### **⚠️ توجه:**

                    - اگر صورت‌های مالی شما متعلق به **یک شرکت** باشند، نمودارها به صورت خودکار رسم می‌شوند.
                    - اگر **چند شرکت مختلف** دارید، می‌توانید شرکت مورد نظر را برای رسم نمودار انتخاب کنید.
                    - اگر نام یک شرکت در سال‌های مختلف **کاملاً تغییر کرده باشد**، می‌توانید شرکت‌ها را به‌صورت دستی ادغام کنید.
                    - در صورت ادغام، تمام شرکت‌های عضو یک گروه، با **نام شرکت اصلی گروه** نمایش داده می‌شوند و شرکت‌های زیرگروه به‌صورت جداگانه نمایش داده نمی‌شوند.

                    </div>
                """, unsafe_allow_html=True)

            
            if st.session_state.results:
                # ✅ استفاده از تابع جدید به جای تابع قدیمی
                create_filtered_charts_section(st.session_state.results)
            else:
                st.info("هنوز فایلی پردازش نشده است.")


    if __name__ == "__main__":
        main()