import streamlit as st
import pandas as pd
st.title('This is a title')
st.markdown('Streamlit is **_really_ cool**.')

genre = st.radio(
     "What's your favorite movie genre",
     ('Comedy', 'Drama', 'Documentary'))

if genre == 'Comedy':
     st.write('You selected comedy.')
else:
    st.write("You didn't select comedy.")
D_Type=st.selectbox(" ",["CSV,TEXT","EXCEL","HTML","XML","JSON","SQL SERVER","MY SQL","SQLite"])
st.markdown('<div style="direction: center; width:100% ; height:40px;margin-left: auto;margin-right: auto"></div> ', unsafe_allow_html=True)



if D_Type=="CSV,TEXT":
    # st.markdown('<div style="color:#black;direction: rtl;font-size: 200%;direction: rtl;font-family: B Nazanin;">آدرس فایل را وارد کنید    </div> ', unsafe_allow_html=True)
    file=st.sidebar.file_uploader('choose your file',type=['csv'])
    
    st.sidebar.subheader("   پارامتر ها   : " )
    delimiters={"comma":",","space":" ","tab":"\t","colon":":","semicolon":";"}
    delimiter=["comma","space","tab","colon","semicolon","سایر موارد"]
    Sep=st.sidebar.radio("separator",delimiter)
    if Sep=="سایر موارد":
        Sep_inp=st.sidebar.text_input("را وارد کنید separator")
    else:
        Sep_inp=delimiters[Sep]
        
    
    st.sidebar.markdown('<div style="direction: rtl;font-size: 200%;direction: rtl"></div> ', unsafe_allow_html=True)
    #UNC=st.sidebar.checkbox("encoding")
    #if UNC:
    encode=st.sidebar.text_input("enter encode")
    if encode:
        encoding=encode
    else:
        encoding=None
        
        
            
    Head= st.sidebar.checkbox("تغییر نام ستون‌ها و تعیین اولین سطر ")
    if Head:
        header=st.sidebar.radio("",["skiprows","header_names"])
        if header=="skiprows":
            number = st.sidebar.number_input('شماره سطر عنوان را وارد کنید',min_value=0, max_value=10,step=1)
            st.sidebar.warning("چنانچه عدد وارد شده غیر صفر باشد سطرهای پیش از عنوان خوانده نمیشوند")

            try:
                data=pd.read_csv(file,sep=Sep_inp,skiprows=number,header=0,encoding=encoding)
            except pd.errors.ParserError:
                data=pd.read_csv(file,sep=Sep_inp,error_bad_lines=False,encoding=encoding)
                print('bad lines skipped')
        if header=="header_names":
            headers=st.sidebar.text_input("h1,h2,...عنوان ستون ها را وارد کنید     ")
            headers =headers.split(",")
            number = st.sidebar.number_input('شماره اولین سطر را وارد کنید',min_value=0, max_value=10,step=1)

            try:
                data=pd.read_csv(file,sep=Sep_inp,header=None,names=headers,skiprows=number,encoding=encoding)
            except pd.errors.ParserError:
                data=pd.read_csv(file,sep=Sep_inp,error_bad_lines=False,encoding=encoding)
                print('bad lines skipped')
                
    else:
        try:
            data=pd.read_csv(file,sep=Sep_inp,skiprows=0,encoding=encoding)
        except pd.errors.ParserError:
            data=pd.read_csv(file,sep=Sep_inp,error_bad_lines=False,encoding=encoding)
            print('bad lines skipped')
    # data
            
st.dataframe(data) 