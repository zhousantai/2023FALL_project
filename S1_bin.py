import warnings
import numpy as np
import pandas as pd
from tqdm import tqdm
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

warnings.simplefilter('ignore')

cat_features = ["B_30", "B_38", "D_114", "D_116", "D_117", "D_120", "D_126", "D_63", "D_64", "D_66", "D_68"]
ignore_features = ["B_30", "B_38", "D_114", "D_116", "D_117",
                   "D_120", "D_126", "D_63", "D_64", "D_66", "D_68", 'S_2', 'customer_ID']


def denoise(df):
    df['D_63'] = df['D_63'].apply(lambda t: {'CR': 0, 'XZ': 1, 'XM': 2, 'CO': 3, 'CL': 4, 'XL': 5}[t]).astype(np.int8)
    df['D_64'] = df['D_64'].apply(lambda t: {np.nan: -1, 'O': 0, '-1': 1, 'R': 2, 'U': 3}[t]).astype(np.int8)
    for col in tqdm(df.columns):
        if col not in ['customer_ID', 'S_2', 'D_63', 'D_64']:
            df[col] = np.floor(df[col] * 100)
    return df


train = pd.read_csv('./input/train_data.csv')
train_y = pd.read_csv('./input/train_labels.csv')

train = denoise(train)
train.fillna(0)
train['y'] = train_y


def decision_tree_binning(df, feature, target, max_leaf_nodes=5):
    """
    对单个特征进行决策树分箱。

    :param df: 包含特征和目标的 DataFrame。
    :param feature: 需要分箱的特征名称。
    :param target: 目标变量的名称。
    :param max_leaf_nodes: 决策树的最大叶子节点数量。
    :return: 分箱后的特征。
    """
    # 分离特征和目标变量
    X = df[[feature]]
    y = df[target]

    # 训练决策树模型
    tree_model = DecisionTreeClassifier(max_leaf_nodes=max_leaf_nodes)
    tree_model.fit(X, y)

    # 使用决策树边界来分箱
    df[f'{feature}_binned'] = pd.cut(x=df[feature], bins=tree_model.tree_.threshold[tree_model.tree_.feature != -2],
                                     right=False, include_lowest=True)

    return df


# 示例使用
# 假设 df 是你的 DataFrame，'feature_to_bin' 是需要分箱的特征，'target' 是目标变量
binned_df = decision_tree_binning(train, train.columns not in ignore_features, 'y')


def GreedyFindBin(distinct_values, counts, num_distinct_values, max_bin, total_cnt, min_data_in_bin=3):
    # INPUT:
    #   distinct_values 保存特征取值的数组，特征取值单调递增
    #   counts 特征的取值对应的样本数目
    #   num_distinct_values 特征取值的数量
    #   max_bin 分桶的最大数量
    #   total_cnt 样本数量
    #   min_data_in_bin 桶包含的最小样本数

    # bin_upper_bound就是记录桶分界的数组
    bin_upper_bound = list()
    assert (max_bin > 0)

    # 特征取值数比max_bin数量少，直接取distinct_values的中点放置
    if num_distinct_values <= max_bin:
        cur_cnt_inbin = 0
        for i in range(num_distinct_values - 1):
            cur_cnt_inbin += counts[i]
            # 若一个特征的取值比min_data_in_bin小，则累积下一个取值，直到比min_data_in_bin大，进入循环。
            if cur_cnt_inbin >= min_data_in_bin:
                # 取当前值和下一个值的均值作为该桶的分界点bin_upper_bound
                bin_upper_bound.append((distinct_values[i] + distinct_values[i + 1]) / 2.0)
                cur_cnt_inbin = 0
        # 对于最后一个桶的上界则为无穷大
        cur_cnt_inbin += counts[num_distinct_values - 1];
        bin_upper_bound.append(float('Inf'))
        # 特征取值数比max_bin来得大，说明几个特征值要共用一个bin
    else:
        if min_data_in_bin > 0:
            max_bin = min(max_bin, total_cnt // min_data_in_bin)
            max_bin = max(max_bin, 1)
        # mean size for one bin
        mean_bin_size = total_cnt / max_bin
        rest_bin_cnt = max_bin
        rest_sample_cnt = total_cnt
        # 定义is_big_count_value数组：初始设定特征每一个不同的值的数量都小（false）
        is_big_count_value = [False] * num_distinct_values
        # 如果一个特征值的数目比mean_bin_size大，那么这些特征需要单独一个bin
        for i in range(num_distinct_values):
            # 如果一个特征值的数目比mean_bin_size大，则设定这个特征值对应的is_big_count_value为真。。
            if counts[i] >= mean_bin_size:
                is_big_count_value[i] = True
                rest_bin_cnt -= 1
                rest_sample_cnt -= counts[i]
        # 剩下的特征取值的样本数平均每个剩下的bin：mean size for one bin
        mean_bin_size = rest_sample_cnt / rest_bin_cnt
        upper_bounds = [float('Inf')] * max_bin
        lower_bounds = [float('Inf')] * max_bin

        bin_cnt = 0
        lower_bounds[bin_cnt] = distinct_values[0]
        cur_cnt_inbin = 0
        # 重新遍历所有的特征值（包括数目大和数目小的）
        for i in range(num_distinct_values - 1):
            # 如果当前的特征值数目是小的
            if not is_big_count_value[i]:
                rest_sample_cnt -= counts[i]
            cur_cnt_inbin += counts[i]

            # 若cur_cnt_inbin太少，则累积下一个取值，直到满足条件，进入循环。
            # need a new bin 当前的特征如果是需要单独成一个bin，或者当前几个特征计数超过了mean_bin_size，或者下一个是需要独立成桶的
            if is_big_count_value[i] or cur_cnt_inbin >= mean_bin_size or \
                    is_big_count_value[i + 1] and cur_cnt_inbin >= max(1.0, mean_bin_size * 0.5):
                upper_bounds[bin_cnt] = distinct_values[i]  # 第i个bin的最大就是 distinct_values[i]了
                bin_cnt += 1
                lower_bounds[bin_cnt] = distinct_values[i + 1]  # 下一个bin的最小就是distinct_values[i + 1]，注意先++bin了
                if bin_cnt >= max_bin - 1:
                    break
                cur_cnt_inbin = 0
                if not is_big_count_value[i]:
                    rest_bin_cnt -= 1
                    mean_bin_size = rest_sample_cnt / rest_bin_cnt
        #             bin_cnt+=1
        # update bin upper bound 与特征取值数比max_bin数量少的操作类似，取当前值和下一个值的均值作为该桶的分界点
        for i in range(bin_cnt - 1):
            bin_upper_bound.append((upper_bounds[i] + lower_bounds[i + 1]) / 2.0)
        bin_upper_bound.append(float('Inf'))
    return bin_upper_bound
