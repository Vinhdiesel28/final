"""Task-specific clarification for personal test-selection questions."""
import re
from services.knowledge_service import normalize

PURPOSES={'first_screening','repeat_abnormal','followup'}
QUESTIONS={
 'purpose':'Bạn muốn sàng lọc tiểu đường lần đầu, kiểm tra lại kết quả bất thường hay theo dõi bệnh đã được chẩn đoán?',
 'symptoms':'Bạn có triệu chứng hoặc vấn đề sức khỏe nào khiến bạn muốn xét nghiệm? Nếu không có, hãy ghi “không có”.',
 'prior_results':'Bạn đã có kết quả xét nghiệm gần đây chưa? Nếu có, ghi tên xét nghiệm, kết quả, đơn vị và thời điểm; nếu chưa, ghi “chưa xét nghiệm”.',
}

def is_testing_guidance(question):
    q=normalize(question)
    selection=bool(re.search(r'\b(?:xet nghiem|kiem tra duong huyet) (?:gi|nao)\b',q))
    if not selection and any(x in q for x in ('nhin an','la gi','phan anh','cho biet')):return False
    if re.search(r'\b(which|what) (?:blood )?tests? (?:should|do|would|must) i\b',q) or 'should i get tested' in q:return True
    if not any(x in q for x in ('xet nghiem','tam soat','sang loc','kiem tra duong huyet')):return False
    return bool(selection or
                re.search(r'\b(?:toi|minh|em|chau)\b.*\b(?:nen|can|muon|di)\b.*\b(?:xet nghiem|tam soat|sang loc)\b',q))

def missing_context(context):
    context=context or {};missing=[]
    if context.get('purpose') not in PURPOSES:missing.append('purpose')
    for key in ('symptoms','prior_results'):
        if not isinstance(context.get(key),str) or not context[key].strip():missing.append(key)
    return missing

def clarify(context):
    fields=missing_context(context)
    answer='Mình cần biết mục đích và bối cảnh trước khi cung cấp thông tin về xét nghiệm phù hợp. '+' '.join(QUESTIONS[k] for k in fields)
    return {'status':'needs_clarification','task':'testing_guidance','requested_fields':fields,
            'questions':[{'field':k,'text':QUESTIONS[k]} for k in fields],
            'answer':answer,'context':context or {},
            'decision':{'status':'needs_clarification','final_label':None,'review_required':False,'reason_codes':['testing_context_missing']}}

def retrieval_question(question,context):
    purpose={
      'first_screening':'Thông tin chung về sàng lọc tiểu đường lần đầu: screening diabetes tests A1C fasting plasma glucose oral glucose tolerance test',
      'repeat_abnormal':'Thông tin chung về xác nhận kết quả xét nghiệm bất thường: confirmation repeat abnormal diabetes test results',
      'followup':'Thông tin chung về theo dõi người đã được chẩn đoán tiểu đường: diabetes monitoring A1C blood glucose',
    }[context['purpose']]
    return question+' '+purpose
