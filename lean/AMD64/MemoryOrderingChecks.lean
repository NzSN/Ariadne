import AMD64.MemoryOrdering

namespace AMD64.MemoryOrdering.Checks

open AMD64.MemoryOrdering
open AMD64.MemoryOrdering.Fixture

theorem locked_publication_orders_wc_data :
    admissibleOrder positiveEvents positiveOrder = true ∧
    publishedBefore positiveEvents positiveOrder positiveRF pData cData = true ∧
    publicationConsistent positiveEvents positiveOrder positiveRF = true := by decide

theorem omitted_synchronization_admits_stale_wc_read :
    admissibleOrder negativeEvents [] = true ∧
    readFromWellFormed negativeEvents [] negativeRF = true ∧
    publishedBefore negativeEvents [] negativeRF nData nStale = false ∧
    nStale.readValue != nData.writeValue := by decide

theorem fences_have_distinct_directions :
    fenceRequired fenceEvents fLoad0 fLoad1 = true ∧
    fenceRequired fenceEvents fStore0 fStore1 = true ∧
    fenceRequired fenceEvents mStore mLoad = true ∧
    fenceRequired lfStoreLoadEvents lfStore lfLoad = false := by decide

theorem lock_transport_uses_type_and_profile_alignment :
    lockTransport release = .cacheableLock ∧
    lockTransport busLockedWC = .busLock ∧
    lockTransport busLockedMisalignedWB = .busLock := by decide

theorem unknown_and_destructive_streaming_are_unavailable :
    supportedEvent unknownLoad = false ∧
    supportedEvent destructiveStream = false := by decide

theorem wb_store_buffering_witness_is_not_globally_sc :
    admissibleOrder storeBufferEvents [] = true ∧
    readFromWellFormed storeBufferEvents [] storeBufferRF = true ∧
    sbLoad0.readValue = 0 ∧ sbLoad1.readValue = 0 := by decide

theorem equal_values_do_not_infer_read_from :
    readFromWellFormed duplicateEvents duplicateOrder duplicateRF = true ∧
    publishedBefore duplicateEvents duplicateOrder duplicateRF dData dRead = false ∧
    readsFrom duplicateRF dRelease2 dAcquire = true := by decide

theorem racing_writer_disables_single_writer_publication_rule :
    readFromWellFormed racingEvents racingOrder racingRF = true ∧
    publishedBefore racingEvents racingOrder racingRF pData racingRead = true ∧
    singleWriterAddress racingEvents pData = false ∧
    readsFrom racingRF racing racingRead = true := by decide

theorem read_from_rejects_self_and_future_sources :
    validRFEdge futureEvents [] futureRF = false ∧
    validRFEdge positiveEvents positiveOrder selfRF = false := by decide

end AMD64.MemoryOrdering.Checks
