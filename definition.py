import http.client, urllib.parse, json

def getTranslation(s):
    "retrieves Naver/Papago NMT translation for the given string"
    #
    failReason = translatedText = ''
    data = urllib.parse.urlencode({"source": "ko", "target": "en", "text": s, })
    headers = {"Content-type": "application/x-www-form-urlencoded; charset=UTF-8",
               "X-Naver-Client-Id": "P3YGzu2suEI1diX0DarY",
               "X-Naver-Client-Secret": "9yhV2ea0wC"}
    conn = http.client.HTTPSConnection("openapi.naver.com")
    conn.request("POST", "/v1/papago/n2mt", data, headers)
    response = conn.getresponse()
    #
    if response.status != 200:
        failReason = response.reason
    else:
        try:
            data = response.read()
            result = json.loads(data).get("message", {}).get("result")
            if result:
                translatedText = result.get('translatedText')
                if not translatedText:
                    failReason = "Naver result missing translateText"
            else:
                failReason = "Naver response missing result"
        except:
            failReason = "Ill-formed JSON response from Naver API"
    conn.close()
    #
    return translatedText, failReason

def getWordDefs(mappedPosList):
    "retrieve definitions for nouns, verbs & adverbs from Naver"
    # pl = [(wpos.split(':')[0], wpos.split(':')[1]) for wpos in posList.split(';')]
    pl = mappedPosList
    wordsToTranslate = [w + ('다' if pos[0] == 'V' else '') for w, pos in pl if pos[0] in ('V', 'N', 'M')]
    words = [w for w, pos in pl if pos[0] in ('V', 'N', 'M')]
    translatedText, failReason = getTranslation('\n'.join(wordsToTranslate))
    if failReason:
        return {}
    else:
        return {w: d.lower().strip('.') for w, d in zip(words, translatedText.split('\n'))}
