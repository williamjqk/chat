#/usr/bin/env python
# -*- coding: utf-8 -*-
# PEP 8 check with Pylint
"""A collection of semantic tools. 语义工具集合。

Use 'jieba' as Chinese word segmentation tool. The 'set_dictionary' and
'load_userdict' must before import 'jieba.posseg' and 'jieba.analyse'.
采用'jieba'作为中文分词工具。

Available functions:
- All classes and functions: 所有类和函数
"""
import os
import codecs
from string import punctuation
import jieba
dictpath = os.path.split(os.path.realpath(__file__))[0]
jieba.set_dictionary(dictpath + "\\dict\\jieba\\synonymdict.txt")
jieba.load_userdict(dictpath + "\\dict\\jieba\\userdict.txt")
import jieba.posseg as posseg
import jieba.analyse as analyse
from numpy import mat, zeros, where

# The 'punctuation_all' is the combination of Chinese and English punctuation.
punctuation_zh = " 、，。°？！：；“”’‘～…【】（）《》｛｝×―－·→℃"
punctuation_all = list(punctuation) + list(punctuation_zh)
# 句尾语气词过滤
tone_words = "。？！的了呢吧吗啊啦"
# 敏感词库 Modified in 2017-5-25
try:
    with codecs.open(dictpath + "\\dict\\swords.txt", "r", "UTF-8") as file:
        sensitive_words = set(file.read().split())
except:
    sensitive_words = []

def generate_swords():
    with codecs.open(dictpath + "\\dict\\sensitive_words.txt", "r", "UTF-8") as file:
        with codecs.open(dictpath + "\\dict\\swords.txt", "w", "UTF-8") as newfile:
            sensitive_words = sorted(list(set(file.read().split())))
            newfile.write("\n".join(sensitive_words))

def check_swords(sentence):
    """检测是否包含敏感词
    """
    for word in sensitive_words:
        if word in sentence:
            return True
    return False
    # words = synonym_cut(sentence, pattern="w")
    # swords = set(sensitive_words).intersection(words)
    # if swords:
        # return True
    # else:
        # return False

def synonym_cut(sentence, pattern="wf"):
    """Cut the sentence into a synonym vector tag.
    将句子切分为同义词向量标签。

    If a word in this sentence was not found in the synonym dictionary,
    it will be marked with default value of the word segmentation tool.
    如果同义词词典中没有则标注为切词工具默认的词性。

    Args:
        pattern: 'w'-分词, 't'-关键词, 'wf'-分词标签, 'tf-关键词标签'。
    """
    sentence = sentence.rstrip(tone_words)
    synonym_vector = []
    if pattern == "w":
        result = list(jieba.cut(sentence))
        synonym_vector = [item for item in result if item not in punctuation_all]
    elif pattern == "t":
        synonym_vector = analyse.extract_tags(sentence, topK=10)
    elif pattern == "wf":
        result = posseg.cut(sentence)
        # synonym_vector = [(item.word, item.flag) for item in result \
        # if item.word not in punctuation_all]
        # Modify in 2017.4.27 
        for item in result:
            if item.word not in punctuation_all:
                if len(item.flag) < 4:
                    item.flag = list(posseg.cut(item.word))[0].flag
                synonym_vector.append((item.word, item.flag))
    elif pattern == "tf":
        result = posseg.cut(sentence)
        tags = analyse.extract_tags(sentence, topK=10)
        for item in result:
            if item.word in tags:
                synonym_vector.append((item.word, item.flag))
    return synonym_vector

def get_tag(sentence, config):
    """
    Get semantic tag of sentence.
    """
    iquestion = sentence.format(**config)
    try:
        keywords = analyse.extract_tags(iquestion, topK=1)
        keyword = keywords[0]
    except IndexError:
        keyword = iquestion
    tags = synonym_cut(keyword, 'wf') # tuple list
    if tags:
        tag = tags[0][1]
        if not tag:
            tag = keyword
    else:
        tag = keyword
    return tag

def sum_cosine(matrix, threshold):
    """Calculate the parameters of the semantic Jaccard model based on the
    Cosine similarity matrix of semantic word segmentation.
    根据语义分词Cosine相似性矩阵计算语义jaccard模型的各个参数。

    Args:
        matrix: Semantic Cosine similarity matrix. 语义分词Cosine相似性矩阵。
        threshold: Threshold for semantic matching. 达到语义匹配标准的阈值。

    Returns:
        total: The semantic intersection of two sentence language fragments.
            两个句子语言片段组成集合的语义交集。
        num_not_match: The total number of fragments or the maximum value of two sets
		    that do not meet the semantic matching criteria controlled by the threshold.
		    两个集合中没有达到语义匹配标准（由阈值threshold控制）的总片段个数或者两者中取最大值。
        total_dif: The degree of semantic difference between two sets.
            两个集合的语义差异程度。
    """
    total = 0
    count = 0
    row = matrix.shape[0]
    col = matrix.shape[1]
    zero_row = zeros([1, col])
    zero_col = zeros([row, 1])
    max_score = matrix.max()
    while max_score > threshold:
        total += max_score
        count += 1
        pos = where(matrix == max_score)
        i = pos[0][0]
        j = pos[1][0]
        matrix[i, :] = zero_row
        matrix[:, j] = zero_col
        max_score = matrix.max()
    num = (row - count) if row > col else (col - count)
    return dict(total=total, num_not_match=num, total_dif=max_score)

def jaccard_basic(synonym_vector1, synonym_vector2):
    """Similarity score between two vectors with basic jaccard.
    两个向量的基础jaccard相似度得分。

    According to the bassic jaccard model to calculate the similarity.
    The similarity score interval for each two sentences was [0, 1].
    根据基础jaccard模型来计算相似度。每两个向量的相似度得分区间为为[0, 1]。
    """
    count_intersection = list(set(synonym_vector1).intersection(set(synonym_vector2)))
    count_union = list(set(synonym_vector1).union(set(synonym_vector2)))
    sim = len(count_intersection)/len(count_union)
    return sim

def jaccard(synonym_vector1, synonym_vector2):
    """Similarity score between two vectors with jaccard.
    两个向量的语义jaccard相似度得分。

    According to the semantic jaccard model to calculate the similarity.
    The similarity score interval for each two sentences was [0, 1].
    根据语义jaccard模型来计算相似度。每两个向量的相似度得分区间为为[0, 1]。
    """
    sv_matrix = []
    sv_rows = []
	# 阈值设定为0.8，每两个词的相似度打分为[0,1]，若无标签则计算原词相似度得分
	# 标签字母前n位相同得分如下
    for word1, tag1 in synonym_vector1:
        for word2, tag2 in synonym_vector2:
            if word1 == word2:
                score = 1.0
            elif tag1 == tag2:
                score = 0.95
            elif tag1[:7] == tag2[:7]:
                score = 0.90
            elif tag1[:6] == tag2[:6]:
                score = 0.86
            elif tag1[:5] == tag2[:5]:
                score = 0.83
            elif tag1[:4] == tag2[:4]:
                score = 0.70
            elif tag1[:3] == tag2[:3]:
                score = 0.60
            elif tag1[:2] == tag2[:2]:
                score = 0.50
            elif tag1[:1] == tag2[:1]:
                score = 0.40
            else:
                score = 0.20
            if score < 0.5:
                jscore = jaccard_basic(list(word1), list(word2))
                if jscore >= 0.5:
                    score = jscore
            sv_rows.append(score)
        sv_matrix.append(sv_rows)
        sv_rows = []
    matrix = mat(sv_matrix)
    result = sum_cosine(matrix, 0.8)
    # result = sum_cosine(matrix, 0.85) # 区分“电脑”和“打印机”：标签前5位相同
    total = result["total"]
    total_dif = result["total_dif"]
    num = result["num_not_match"]
    sim = total/(total + num*(1-total_dif))
    return sim

def edit_distance(synonym_vector1, synonym_vector2):
    """Similarity score between two vectors with edit distance.
    根据语义编辑距离计算相似度。
    """
    sim = 1
    print(synonym_vector1, synonym_vector2)
    # print(str(sim))
    return sim

def similarity(synonym_vector1, synonym_vector2, pattern='j'):
    """Similarity score between two sentences.
    两个向量的相似度得分。

    Args:
        pattern: Similarity computing model. 相似度计算模式。
            Defaults to 'j' represents 'jaccard'.
    """
    assert synonym_vector1 != [], "synonym_vector1 can not be empty"
    assert synonym_vector2 != [], "synonym_vector2 can not be empty"
    if synonym_vector1 == synonym_vector2:
        return 1.0
    if pattern == 'jb':
        sim = jaccard_basic(synonym_vector1, synonym_vector2)
    elif pattern == 'j':
        sim = jaccard(synonym_vector1, synonym_vector2)
    elif pattern == 'e':
        sim = edit_distance(synonym_vector1, synonym_vector2)
    return sim

def get_location(sentence):
    """Get location in sentence.
    """
    location = []
    sv_sentence = synonym_cut(sentence, 'wf')
    for word, tag in sv_sentence:
        if tag.startswith("Di02") or tag.startswith("Di03") or tag == "Cb25A11#":
            location.append(word)
    return location

def get_musicinfo(sentence):
    """Get music info in sentence.
    """
    words = sentence.lstrip("唱一首").split("的")
    singer = words[0]
    song = words[1]
    return (singer, song)
