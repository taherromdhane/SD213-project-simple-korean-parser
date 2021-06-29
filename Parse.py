import re, json
from pprint import pprint, pformat
from datetime import datetime

from tagmap import TagMap
from chunker import Chunker
from definition import getWordDefs

from konlpy.tag import Kkma

def buildParseTree(chunkTree, showAllLevels=False):
    "constructs display structures from NLTK chunk-tree"
    # first, recursively turn the chunk tree into a Python nested dict so it can be JSONified
    #  gathering terminals list & adding level from root & parent links along the way
    terminals = []; height = [0]; allNodes = []; nodeIDs = {}
    def asDict(chunk, parent=None, level=0, isLastChild=False):
        height[0] = max(height[0], level)
        if not showAllLevels:
            # elide degenerate tree nodes (those with singleton children)
            while isinstance(chunk, nltk.Tree) and len(chunk) == 1:
                chunk = chunk[0]
        if isinstance(chunk, nltk.Tree):
            tag = chunk.label()
            # ad-hoc label mappings
            if tag == 'S':
                tag = 'Sentence'
            elif tag == 'Predicate' and not isLastChild:
                tag = 'Verb Phrase'
            # build tree node
            node = dict(type='tree', tag=tag, level=level, layer=1, parent=parent)
            node['children'] = [asDict(c, node, level+1, isLastChild=i == len(chunk)-1) for i, c in enumerate(chunk)]
            nodeID = nodeIDs.get(id(node))
            if not nodeID:
                nodeIDs[id(node)] = nodeID = len(nodeIDs) + 1
            node['id'] = nodeID
            allNodes.append(node)
            return node
        else:
            word = chunk[0].strip()
            tag = chunk[1]
            tm = TagMap.POS_labels.get(word + ":" + tag)
            tagLabel = (tm.posLabel if tm else TagMap.partsOfSpeech.get(tag)[0]).split('\n')
            node = dict(type='word', word=word, tag=tag, tagLabel=tagLabel, children=[], parent=parent, level=-1, layer=0)
            nodeID = nodeIDs.get(id(node))
            if not nodeID:
                nodeIDs[id(node)] = nodeID = len(nodeIDs) + 1
            node['id'] = nodeID
            terminals.append(node)
            allNodes.append(node)
            return node
    tree = asDict(chunkTree)


def parse():
    "parse POSTed Korean sentence"
    # grab sentence to parse
    input = request.form.get('sentence')
    if not input:
        return jsonify(result="FAIL", msg="Missing input sentence(s)")
    showAllLevels = request.form.get('showAllLevels') == 'true'

    # parse input & return parse results to client
    sentences = parseInput(input, parser="RD", showAllLevels=showAllLevels)

    return jsonify(result="OK",
                   sentences=sentences)

def parseInput(input, parser="RD", showAllLevels=False, getWordDefinitions=True):
    "parse input string into list of parsed contained sentence structures"
    # parser can be RD for recusrsive descent (currently the most-developed) or "NLTK" for the original NLTK chunking-grammar parser

    # clean & build a string for the KHaiii phoneme analyzer
    input = input.strip()
    if input[-1] not in ['.', '?', '!']:
        input += '.'
    input = re.sub(r'\s+([\.\?\;\,\:])', r'\1', input)  # elide spaces preceding clause endings, throws Khaiii off
    # input = input.replace(',', ' , ').replace(';', ' ; ').replace(':', ' : ') - adding a space before punctuation seems to mess tagging in Khaiii
    print("* parse {0}".format(input))

    # run Khaiii, grab the parts-of-speech list it generates (morphemes + POS tags) and extract original word-to-morpheme groupings
    sentences = []  # handle possible multiple sentences
    posList = []; morphemeGroups = []
    kkma_parser = Kkma()

    for w in input.split(" "):
        morphs = kkma_parser.pos(w)
        morphemeGroups.append([w, [m[0] for m in morphs if m[1] != 'SF']])
        for m in morphs:
            tag = m[1]
            if tag == "ETD" :
                tag = "ETM"
            if tag == "EFN" :
                tag = "EF"
            posList.append('{0}:{1}'.format(m[0].strip(), tag))
            if m[1] == 'SF':
                # sentence end, store extractions & reset for possible next sentence
                sentences.append(dict(posList=posList, morphemeGroups=morphemeGroups, posString=';'.join(posList)))
                posList = []; morphemeGroups = []

    for s in sentences:
        # map POS through synthetic tag mapper & extract word groupings
        mappedPosList, morphemeGroups = TagMap.mapTags(s['posString'], s['morphemeGroups']) #, disableMapping=True)
        print("  {0}".format(s['posString']))
        print("  mapped to {0}".format(mappedPosList))

        if parser == "NLTK":  # NLTK chunking parser
            # perform chunk parsing
            chunkTree = Chunker.parse(mappedPosList, trace=2)
            chunkTree.pprint()
            # apply any synthetic-tag-related node renamings
            TagMap.mapNodeNames(chunkTree)
            # extract popup wiki definitions & references links & notes for implicated nodes
            references = TagMap.getReferences(chunkTree)
            # build descriptive phrase list
            phrases = Chunker.phraseList(chunkTree)
            #
            parseTreeDict = buildParseTree(chunkTree, showAllLevels=showAllLevels)

        else:  # recursive-descent parser
            from rd_grammar import KoreanParser
            parser = KoreanParser([":".join(p) for p in mappedPosList])
            parseTree = parser.parse(verbose=0)
            print("parse tree : ", parseTree)
            if parseTree:
                # apply any synthetic-tag-related node renamings
                parseTree.mapNodeNames()
                # extract popup wiki definitions & references links & notes for implicated nodes
                references = parseTree.getReferences()
                # build descriptive phrase list
                phrases = parseTree.phraseList()
                # get noun & verb translations from Naver
                wordDefs = getWordDefs(mappedPosList) if getWordDefinitions else {}
                print(mappedPosList)
                print("word definitions :\n", wordDefs)
                # build JSONable parse-tree dict
                parseTreeDict = parseTree.buildParseTree(wordDefs=wordDefs, showAllLevels=showAllLevels)
                print("  {0}".format(parseTree))
            else:
                # parsing failed, return unrecognized token
                parseTree = references = parseTreeDict = phrases = None
                s.update(dict(error="Sorry, failed to parse sentence",
                              lastToken=parser.lastTriedToken()))
                print("  ** failed.  Unexpected token {0}".format(parser.lastTriedToken()))

        # format debugging daat
        debugging = dict(posList=pformat(s['posList']),
                         mappedPosList=pformat(mappedPosList),
                         phrases=pformat(phrases),
                         morphemeGroups=pformat(morphemeGroups),
                         parseTree=pformat(parseTreeDict),
                         references=references)

        # add parsing results to response structure
        s.update(dict(mappedPosList=mappedPosList,
                      morphemeGroups=morphemeGroups,
                      parseTree=parseTreeDict,
                      references=references,
                      phrases=phrases,
                      debugging=debugging
                      ))
    #
    return sentences