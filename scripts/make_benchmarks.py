"""Build original, small repair fixtures. No third-party source or benchmark data.

The corpus is intentionally didactic: public regression tests and separately held
oracle tests. Candidate variants are authored examples, never claimed as LLM output.
"""
from pathlib import Path
import json
import textwrap

ROOT=Path(__file__).resolve().parents[1]
tasks=[]

def add(ident,family,title,issue,params,body,good,public,oracle,partial=None,compact=None):
    source="def solve("+params+"):\n"+textwrap.indent(textwrap.dedent(body).strip(),"    ")+"\n"
    fixed="def solve("+params+"):\n"+textwrap.indent(textwrap.dedent(good).strip(),"    ")+"\n"
    # Build a deliberately overfitted proposal from public examples only.
    names=[n.strip().split("=")[0].strip() for n in params.split(",")]
    key="repr(("+", ".join(names)+",))"
    table={repr(tuple(c[0])):c[1] for c in public if len(c)==2}
    overfit="def solve("+params+"):\n    lookup = "+repr(table)+"\n    return lookup.get("+key+")\n"
    first=public[0][1]
    constant="def solve("+params+"):\n    return "+repr(first)+"\n"
    partial_code="def solve("+params+"):\n"+textwrap.indent(textwrap.dedent(partial or body).strip(),"    ")+"\n"
    alternative="def solve("+params+"):\n"+textwrap.indent(textwrap.dedent(compact or good).strip(),"    ")+"\n"
    # Comments are varied without introducing task labels as model features.
    alternative=alternative.replace("\n    ","\n    # Preserve the behavior outside the reported example.\n    ",1)
    variants=[{"name":"Focused implementation","code":fixed},
              {"name":"Case-specific replacement","code":overfit},
              {"name":"Early-return alternative","code":constant},
              {"name":"Partial adjustment","code":partial_code},
              {"name":"Alternative implementation","code":alternative},
              {"name":"Original implementation","code":source}]
    # Deterministic permutation prevents position from leaking correctness.
    import random
    random.Random(ident).shuffle(variants)
    tasks.append({"id":ident,"family":family,"title":title,"issue":issue,"source":source,
                  "public":public,"oracle":oracle,"candidates":variants})

# Three unrelated repair problems per family; all family members share a split.
add("pagination","slicing","Pagination drops the last item","Fix paginate: page is zero-based, size positive, preserve short final pages.","items, page, size",
    "start = page * size\nreturn items[start:start + size - 1]","start = page * size\nreturn items[start:start + size]",
    [([[1,2,3,4],0,2],[1,2]),([[1,2,3,4],1,2],[3,4]),([[],0,3],[])],
    [([[8,9,10],1,2],[10]),([[7],0,1],[7]),([[1,2],5,2],[]),([[7],0,3],[7])],
    "return items[page * size:(page + 1) * size] if len(items) >= size else []")
add("chunks","slicing","Chunking skips a partial batch","Split a list into consecutive chunks including the final incomplete chunk. size is positive.","items, size",
    "return [items[i:i+size] for i in range(0,len(items)-size+1,size)]",
    "return [items[i:i+size] for i in range(0,len(items),size)]",
    [([[1,2,3,4,5],2],[[1,2],[3,4],[5]]),([[],2],[]),([[1,2],2],[[1,2]])],
    [([[5],4],[[5]]),([[2,3,4],1],[[2],[3],[4]]),([[9,8,7,6],3],[[9,8,7],[6]])],
    "return [items[i:i+size] for i in range(0,len(items),size)] if len(items) > 1 else []")
add("tail","slicing","Zero-length tail returns the entire list","Return at most n trailing values. n <= 0 must return an empty list.","items, n",
    "return items[-n:]","return items[-n:] if n > 0 else []",
    [([[1,2,3],0],[]),([[1,2,3],2],[2,3]),([[],2],[])],
    [([[1,2],-1],[]),([[1],9],[1]),([[2,3],1],[3])],"return [] if n == 0 else items[-n:]")
add("mean","arithmetic","Mean rounds down decimals","Return the arithmetic mean as a number, or 0.0 for an empty list.","values",
    "return sum(values) // len(values) if values else 0.0","return sum(values) / len(values) if values else 0.0",
    [([[1,2]],1.5),([[]],0.0),([[3,6]],4.5)],
    [([[-1,0]],-0.5),([[1,2,4]],7/3),([[8]],8.0)],"return round(sum(values) / len(values), 1) if values else 0.0")
add("median","arithmetic","Even-length median chooses one element","Return the median of numeric values; empty input gives None. Do not mutate the input.","values",
    "if not values: return None\ns = sorted(values)\nreturn s[len(s)//2]",
    "if not values: return None\ns = sorted(values)\nm = len(s)//2\nreturn s[m] if len(s)%2 else (s[m-1]+s[m])/2",
    [([[1,4]],2.5),([[4,1,2]],2),([[]],None)],
    [([[7,1,3,9]],5.0),([[0]],0),([[-3,-2]],-2.5)],
    "if not values: return None\ns = sorted(values)\nreturn sum(s)/len(s)")
add("discount","arithmetic","Percentage discount is interpreted as a multiplier","Given nonnegative price and discount percent in [0,100], return discounted price rounded to two decimals.","price, percent",
    "return round(price * (1 - percent), 2)","return round(price * (1 - percent / 100), 2)",
    [([100,20],80.0),([80,25],60.0),([10,0],10.0)],
    [([19.99,10],17.99),([42,100],0.0),([0,15],0.0)],"return round(price - percent, 2)")
add("slug","strings","Slug retains surrounding separators","Lowercase the words of a string, collapse whitespace to hyphens, and remove surrounding whitespace.","text",
    "return text.lower().replace(' ', '-')","return '-'.join(text.lower().split())",
    [([" Hello  World "],"hello-world"),(["Already"],"already"),([""],"")],
    [(["A\tB\nC"],"a-b-c"),(["  x "],"x"),(["a   b"],"a-b")],"return text.strip().lower().replace('  ', ' ').replace(' ', '-')")
add("prefix","strings","Prefix remover removes internal occurrences","Remove prefix only when it appears at the start of text; empty prefix leaves text unchanged.","text, prefix",
    "return text.replace(prefix, '')","return text[len(prefix):] if prefix and text.startswith(prefix) else text",
    [(["pre-prefix","pre-"],"prefix"),(["xpre-value","pre-"],"xpre-value"),(["hello",""],"hello")],
    [(["aaa","a"],"aa"),(["test","z"],"test"),(["abcabc","abc"],"abc")],"return text.replace(prefix, '', 1)")
add("initials","strings","Initials split fails on repeated whitespace","Return uppercase initials of whitespace-delimited words; blank input gives an empty string.","name",
    "return ''.join(part[0].upper() for part in name.split(' '))","return ''.join(part[0].upper() for part in name.split())",
    [([" Ada  Lovelace "],"AL"),(["Grace Hopper"],"GH"),([""],"")],
    [(["a\tb"],"AB"),(["  "],""),(["single"],"S")],"return ''.join(part[0].upper() for part in name.split(' ') if part)")
add("unique","collections","Deduplication changes order","Deduplicate hashable values, keeping the first occurrence and preserving input order.","values",
    "return sorted(set(values))","return list(dict.fromkeys(values))",
    [([[3,1,3,2]],[3,1,2]),([[]],[]),([[2,2]],[2])],
    [([[9,8,9,7]],[9,8,7]),([["b","a","b"]],["b","a"]),([[0,-1,0]],[0,-1])],"return list(set(values))")
add("counts","collections","Counter ignores repeated values","Return a dictionary counting every value in a list of strings.","values",
    "return {x: 1 for x in values}","counts = {}\nfor value in values:\n    counts[value] = counts.get(value, 0) + 1\nreturn counts",
    [([["a","a","b"]],{"a":2,"b":1}),([[]],{}),([["x"]],{"x":1})],
    [([["x","x","x"]],{"x":3}),([["a","b","a","b"]],{"a":2,"b":2}),([[""]],{"":1})],
    "return {x: min(values.count(x), 2) for x in values}")
add("flatten","collections","Flatten keeps only the first nested list","Flatten one level of lists while preserving order, including empty nested lists.","groups",
    "return groups[0] if groups else []","return [x for group in groups for x in group]",
    [([[[1,2],[3]]],[1,2,3]),([[]],[]),([[[],[4]]],[4])],
    [([[[1],[],[2],[3]]],[1,2,3]),([[[],[]]],[]),([[["a"],["b"]]],["a","b"])],
    "return sum(groups[:2], [])")
add("clamp","boundaries","Clamp reverses the lower and upper bound","Clamp x to inclusive [lower,upper]. Assume lower <= upper.","x, lower, upper",
    "return max(upper, min(lower, x))","return min(upper, max(lower, x))",
    [([5,0,10],5),([-1,0,10],0),([20,0,10],10)],
    [([-8,-10,-5],-8),([4,4,4],4),([0.5,0,1],0.5)],"return max(lower,x)")
add("overlap","boundaries","Half-open intervals count touching edges","For nonempty half-open intervals [a,b) and [c,d), report whether they overlap.","a, b, c, d",
    "return max(a,c) <= min(b,d)","return max(a,c) < min(b,d)",
    [([1,3,3,5],False),([1,4,2,6],True),([1,2,4,5],False)],
    [([-3,0,0,2],False),([0,10,2,3],True),([2,3,0,10],True)],"return a < c < b")
add("expiry","boundaries","Token remains valid at its exact expiry","A token is expired when now is greater than or equal to expiry. Both timestamps are numeric.","now, expiry",
    "return now > expiry","return now >= expiry",
    [([100,100],True),([99,100],False),([101,100],True)],
    [([0,0],True),([-1,0],False),([1.25,1.25],True),([0.1,0.9],False)],"return int(now) >= int(expiry)")
add("parse-bool","parsing","Boolean parser treats false strings as truthy","Trim and lowercase a string. True forms: true,yes,1,on. False forms: false,no,0,off. Other strings return None.","text",
    "return bool(text)","value = text.strip().lower()\nif value in ('true','yes','1','on'): return True\nif value in ('false','no','0','off'): return False\nreturn None",
    [(["true"],True),(["false"],False),(["unknown"],None)],
    [([" YES "],True),(["0"],False),(["On"],True),([""],None)],
    "if text == 'true': return True\nif text == 'false': return False\nreturn None")
add("csv-integers","parsing","Integer parser fails on empty fields","Parse comma-separated integers, ignoring blank fields and surrounding whitespace.","text",
    "return [int(x) for x in text.split(',')]","return [int(x.strip()) for x in text.split(',') if x.strip()]",
    [(["1,,2"],[1,2]),([""],[]),(["3,4"],[3,4])],
    [([" , -5, 0, "],[-5,0]),([",,,"],[]),(["12"],[12])],"return [int(x) for x in text.split(',') if x]")
add("key-value","parsing","Key-value parser splits values containing equals","Parse first '=' into a stripped key and value. A line without '=' returns None.","line",
    "parts = line.split('=')\nreturn [parts[0], parts[1]] if len(parts)==2 else None",
    "if '=' not in line: return None\nkey, value = line.split('=', 1)\nreturn [key.strip(), value.strip()]",
    [(["name=alice"],["name","alice"]),(["url=a=b"],["url","a=b"]),(["none"],None)],
    [([" x = y "],["x","y"]),(["a="],["a",""]),(["=x=y"],["","x=y"])],
    "if '=' not in line: return None\nreturn line.split('=',1)")
add("weighted","statistics","Weighted mean divides by observation count","Return weighted mean of value/weight pairs, or 0.0 when total weight is zero.","pairs",
    "return sum(v*w for v,w in pairs)/len(pairs) if pairs else 0.0",
    "weight = sum(w for _,w in pairs)\nreturn sum(v*w for v,w in pairs)/weight if weight else 0.0",
    [([[[10,1],[20,3]]],17.5),([[]],0.0),([[[3,0]]],0.0)],
    [([[[5,2]]],5.0),([[[1,1],[3,1]]],2.0),([[[4,0],[7,2]]],7.0),([[[1,1],[2,2]]],5/3)],
    "weight = sum(w for _,w in pairs)\nreturn round(sum(v*w for v,w in pairs)/weight,1) if weight else 0.0")
add("moving-mean","statistics","Moving average has an off-by-one window","Return the mean of each full consecutive window. width positive; fewer elements than width yields [].", "values, width",
    "return [sum(values[i:i+width])/width for i in range(len(values)-width)]",
    "return [sum(values[i:i+width])/width for i in range(len(values)-width+1)]",
    [([[1,2,3],2],[1.5,2.5]),([[1],2],[]),([[4,6],2],[5.0])],
    [([[1,2,3],1],[1.0,2.0,3.0]),([[],3],[]),([[2,4,6,8],3],[4.0,6.0])],
    "return [sum(values[i:i+width])/width for i in range(0,len(values)-width+1,width)]")
add("variance","statistics","Population variance uses sample denominator","Return population variance; empty list gives 0.0.","values",
    "if len(values)<2: return 0.0\nmean = sum(values)/len(values)\nreturn sum((v-mean)**2 for v in values)/(len(values)-1)",
    "if not values: return 0.0\nmean = sum(values)/len(values)\nreturn sum((v-mean)**2 for v in values)/len(values)",
    [([[1,3]],1.0),([[]],0.0),([[2]],0.0)],
    [([[1,2,3]],2/3),([[5,5]],0.0),([[-2,2]],4.0)],
    "if not values: return 0.0\nmean = sum(values)/len(values)\nreturn round(sum((v-mean)**2 for v in values)/len(values),1)")
add("merge","ordering","Sorted merge discards duplicates","Combine two sorted lists into one sorted list, retaining every occurrence.","left, right",
    "return sorted(set(left + right))","return sorted(left + right)",
    [([[1,2],[2,3]],[1,2,2,3]),([[],[1]],[1]),([[],[]],[])],
    [([[2,2],[2]],[2,2,2]),([[-1,5],[-2,3]],[-2,-1,3,5]),([[1],[]],[1]),([[1],[2,2]],[1,2,2])],"return sorted(left + list(set(right)))")
add("top-k","ordering","Top-k returns smallest scores","Return the k largest numbers in descending order, preserving duplicates. k <= 0 returns [].", "values, k",
    "return sorted(values)[:k]","return sorted(values, reverse=True)[:k] if k > 0 else []",
    [([[1,5,3],2],[5,3]),([[2,2,1],2],[2,2]),([[],3],[])],
    [([[1,3],-1],[]),([[7],0],[]),([[2,9],5],[9,2])],"return sorted(values, reverse=True)[:k]")
add("stable-sort","ordering","Record sorter uses descending score","Sort [name,score] records by ascending score and preserve original order on ties.","records",
    "return sorted(records, key=lambda r: r[1], reverse=True)","return sorted(records, key=lambda r: r[1])",
    [([[["b",2],["a",1]]],[["a",1],["b",2]]),([[]],[]),([[["x",1]]],[["x",1]])],
    [([[["z",2],["a",2],["m",1]]],[["m",1],["z",2],["a",2]]),([[["b",0],["a",0]]],[["b",0],["a",0]])],
    "return sorted(records, key=lambda r: (r[1],r[0]))")

out=ROOT/"data/benchmarks.json"
out.write_text(json.dumps({"version":1,"license":"MIT","provenance":"Original authored repair fixtures; not real GitHub issues or SWE-bench", "tasks":tasks},indent=2)+"\n")
print(f"Wrote {len(tasks)} tasks and {sum(len(t['candidates']) for t in tasks)} authored candidates")
