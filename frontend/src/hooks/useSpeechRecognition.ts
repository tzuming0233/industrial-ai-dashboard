import { useCallback, useEffect, useRef, useState } from 'react'

// 표준 TS DOM 타입에는 아직 Web Speech API가 없어서 최소한만 선언한다.
interface SpeechRecognitionResultLike {
  isFinal: boolean
  0: { transcript: string }
}
interface SpeechRecognitionEventLike extends Event {
  resultIndex: number
  results: ArrayLike<SpeechRecognitionResultLike>
}
interface SpeechRecognitionLike extends EventTarget {
  lang: string
  continuous: boolean
  interimResults: boolean
  start: () => void
  stop: () => void
  onresult: ((ev: SpeechRecognitionEventLike) => void) | null
  onerror: ((ev: Event) => void) | null
  onend: (() => void) | null
}

function getRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike
    webkitSpeechRecognition?: new () => SpeechRecognitionLike
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export function useSpeechRecognition(onFinalText: (text: string) => void) {
  const [지원됨] = useState(() => getRecognitionCtor() !== null)
  const [듣는중, set듣는중] = useState(false)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const onFinalTextRef = useRef(onFinalText)
  onFinalTextRef.current = onFinalText

  useEffect(() => {
    return () => recognitionRef.current?.stop()
  }, [])

  const 시작 = useCallback(() => {
    const Ctor = getRecognitionCtor()
    if (!Ctor) return
    const recognition = new Ctor()
    recognition.lang = 'ko-KR'
    recognition.continuous = true
    recognition.interimResults = false
    recognition.onresult = (ev) => {
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const 결과 = ev.results[i]
        if (결과.isFinal) onFinalTextRef.current(결과[0].transcript)
      }
    }
    recognition.onerror = () => set듣는중(false)
    recognition.onend = () => set듣는중(false)
    recognitionRef.current = recognition
    recognition.start()
    set듣는중(true)
  }, [])

  const 중지 = useCallback(() => {
    recognitionRef.current?.stop()
    set듣는중(false)
  }, [])

  const 토글 = useCallback(() => {
    if (듣는중) 중지()
    else 시작()
  }, [듣는중, 시작, 중지])

  return { 지원됨, 듣는중, 토글 }
}
