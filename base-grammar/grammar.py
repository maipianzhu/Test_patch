str = "Hello World"

print(str)

str = "123456789"

print(str)  # 输出字符

# 字符串操作 var1:起始 var2:结束 var3:步长
print(str[0:-1:3])

# 基本数据类型
a, b, c = 1, 2, "abc"

print(type(a))
print(type(b))
print(type(c))

print(a)
print(b)
print(c)

# type() 和 isinstance()
is_true = True
num1 = 1

print(isinstance(is_true, int))

# 列表操作: insert, pop, append 对比
print("\n--- 列表操作演示 ---")
my_list = ["a", "b", "c"]
print("初始列表:", my_list)

# 1. append: 在列表末尾添加元素
my_list.append("d")
print("append('d') 后:", my_list)

# 2. insert: 在指定索引位置插入元素
my_list.insert(1, "x")
print("insert(1, 'x') 后:", my_list)

# 3. pop: 删除并返回指定索引的元素 (默认最后一个)
p1 = my_list.pop()
print(f"pop() 后 (默认删末尾): {my_list}, 被删元素: {p1}")

p2 = my_list.pop(1)
print(f"pop(1) 后 (删索引1): {my_list}, 被删元素: {p2}")  # True

# 列表
list_a = [1, 2, 3, 4, 5]  # list
tuple_a = (1, 2, 3, 4, 5)  # list.of
set_a = {1, 2, 3, 4, 5}  # set
dict_a = {1: "a", 2: "b", 3: "c", 4: "d", 5: "e"}  # map

# 容器初始化对比
print("\n--- 容器初始化与特殊情况演示 ---")

# 1. 空集合 (Set) vs 空字典 (Dict)
# {} 默认是空字典，不是空集合！这是最大的坑
empty_dict = {}
empty_set = set()  # 必须用 set()

print(f"{{}} 的类型: {type(empty_dict)}")  # <class 'dict'>
print(f"set() 的类型: {type(empty_set)}")  # <class 'set'>

# 2. 其他容器的空初始化 ([] 和 () 可以直接用)
empty_list = []
empty_tuple = ()
print(f"[] 的类型: {type(empty_list)}")
print(f"() 的类型: {type(empty_tuple)}")

# 3. 特殊情况：单个元素的元组
# (1) 只是数字，(1,) 才是元组
tuple_trap_1 = 1
tuple_correct = (1,)
print(f"(1) 的类型: {type(tuple_trap_1)}")  # <class 'int'>
print(f"(1,) 的类型: {type(tuple_correct)}")  # <class 'tuple'>

# frozenset vs tuple (猜测你指的可能是 tuple) 对比
print("\n--- frozenset (冻结集合) vs tuple (元组) ---")

# 1. 定义与特性
# Tuple (元组): "不可变的列表" -> 有序、可重复
t_obj = (1, 2, 2, 3)
print(f"Tuple (有序,可重复): {t_obj}")

# Frozenset (冻结集合): "不可变的集合" -> 无序、唯一(自动去重)
fs_obj = frozenset([1, 2, 2, 3])
print(f"Frozenset (无序,唯一): {fs_obj}")

# 2. 它们共同点：都不可变 (Immutable)
# t_obj[0] = 9     # 报错! TypeError
# fs_obj.add(4)    # 报错! AttributeError

# 3. 核心应用场景：都可以做字典的 Key
# 普通的 list 和 set 是不能做 dict key 的，因为它们可变
valid_dict = {t_obj: "Tuple是个好Key", fs_obj: "Frozenset也是个好Key"}
print("字典Key测试成功:", valid_dict)
