import QtQml.StateMachine 1.0 as DSM
import Resonance 3.0

DSM.StateMachine {
    id: root
    initialState: st_initial

    property string hdfFileName: 'keklol-$$.hdf5'
    property string eegMode: 'Normal' // EEG recording mode
	//property string eventStreamDiscovery: 'discover:///?stream=events&name=WorkflowControler' //WHAT IS IT?? 

    property int eegRecordCounter: 1 // WHAT IS IT?? 
	
	property bool use_nvx: false
	property bool use_speed: false

    property string service_name: "nvx136" //"signalGenerator"
    property string stream_name: "eeg" //"generated"

    property alias runningRecord: stRECORD_running.active // идёт запись ээг, если находится в состоянии stRECORD_running

    signal startRecord  // WHAT IS IT? to mark the start eeg recording?
    signal finish // WHAT IS IT? to mark the end of eeg recording?
    signal startEeg // not sure if i still need it
	
	signal startedEeg

    Recorder { // WHAT IS IT??? another qml??..
        id: recorder
    }

    DSM.State { // INITIAL STATE
        id: st_initial
		
		onEntered: {
            print(stream_name, service_name)
            recorder.openFile(root.hdfFileName)
		}
		
        DSM.SignalTransition {
            signal: st_initial.entered
            targetState: stRECORD_add_streams
        }

    }
	

    DSM.State {
        id: st_launched
		
        DSM.SignalTransition {
            signal: root.finish
            targetState: st_final
        }

        DSM.State {
            id: st_record
            initialState: stRECORD_add_streams


            DSM.State {
                id: stRECORD_add_streams

                onEntered: {
                    //if (root.use_nvx) {recorder.addStream(
                    //    "discover:///?stream=" + stream_name + "&name=" + service_name,
                    //    stream_name                    )}
                    recorder.addStream('discover:///?stream=eeg&name=nvx136', 'eeg')

                    let service = ResonanceApp.getService("TEP_visual");
                    if (service) {recorder.addStream('discover:///?stream=stimuli&name=TEP_visual', 'stimuli');}

                    //recorder.addStream('discover:///?stream=eeg&name=nvx136', 'eeg')

                    //if (root.use_speed) {recorder.addStream('discover:///?stream=naive_probability&name=SPEED')}
					
					root.eegRecordCounter += 1 // ЗАЧЕМ ЭТОТ СЧЁТЧИК???
                }

                DSM.SignalTransition { // what is it?..
                    signal: recorder.streamsChanged
                    guard: {
                        let nvx1Found = false;
                        let nvx1 = ResonanceApp.getService('nvx136');

                        recorder.recording.forEach((info) => {
                            if(info.uid === nvx1.uid){
                                nvx1Found = true;
                            }
                        } )

                        return nvx1Found;
                    }
                    targetState: stRECORD_running
                }
            }

			DSM.State {
				id: stRECORD_running

				onEntered: { root.startedEeg()} // WHAT IS IT??? 

				DSM.SignalTransition {
					signal: root.finish // the stop signal from a button
					targetState: st_final
				}

			}
        }
	}
	
	DSM.FinalState {
		id: st_final
		onEntered: { recorder.closeFile()}
	}
	
}
