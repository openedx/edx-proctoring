export const handlerWrapper = (Handler) => {
   let handler = new Handler({});

  self.addEventListener("message", (message) => {
    switch(message.data.type) {
      case 'config': {
        handler = new Handler(message.data.options);
        break;
      }
      case 'startExamAttempt': {
        if(handler.onStartExamAttempt) {
          handler.onStartExamAttempt().then(() => self.postMessage({type: 'examAttemptStarted'}))
        }
        break;
      }
      case 'endExamAttempt': {
        if(handler.onEndExamAttempt) {
          handler.onEndExamAttempt().then(() => self.postMessage({type: 'examAttemptEnded'}))
        }
        break;
      }
      case 'ping': {
        if(handler.onPing) {
          handler.onPing().then(() => self.postMessage({type: 'echo'}))
        }
        break;
      }
    }
  });

}
export default handlerWrapper;
