#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Oct  7 15:21:55 2018

@author: mishugeb
"""
# This source code file is a part of SigProfilerExtractor
# SigProfilerExtractor is a tool included as part of the SigProfiler
# computational framework for comprehensive analysis of mutational
# signatures from next-generation sequencing of cancer genomes.
# SigProfilerExtractor allows de novo extraction of mutational 
#signatures from data generated in a matrix format. The tool 
#identifies the number of operative mutational signatures, 
#their activities in each sample, and the probability for each 
#signature to cause a specific mutation type in a cancer sample. 
#The tool makes use of SigProfilerMatrixGenerator and SigProfilerPlotting.
# Copyright (C) 2018 S M Ashiqul Islam (Mishu)
#
# SigProfilerExtractor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SigProfilerExtractor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SigProfilerExtractor.  If not, see http://www.gnu.org/licenses/



import matplotlib.pyplot as plt
plt.switch_backend('agg')
import nimfa 
import numpy as np
import pandas as pd
from sklearn import metrics
import time
import multiprocessing
from functools import partial
from scipy.optimize import minimize
from numpy import linalg as LA
from random import shuffle
import sigProfilerPlotting as plot
import string 
import os
os.environ["MKL_NUM_THREADS"] = "1" 
os.environ["NUMEXPR_NUM_THREADS"] = "1" 
os.environ["OMP_NUM_THREADS"] = "1"


def extract_arrays(data, field, index=True):
    accumulator = list()
    if index==False:
        for i in data[field]:
            accumulator.append(i)
        return accumulator 
    else:        
        for i in data[field]:
            accumulator.append(i[0][0])
        return accumulator 

def extract_input(data):         
    originalGenome=data['originalGenomes']        
    cancerType = extract_arrays(data, 'cancerType', False)
    sampleNames = extract_arrays(data, 'sampleNames', True)
    subTypes = extract_arrays(data, 'subtypes', True)
    types = extract_arrays(data, 'types', True)
    allFields = [cancerType, originalGenome, sampleNames, subTypes, types]
    return allFields


def nnmf(genomes, nfactors):
    genomes = np.array(genomes)
    nmf = nimfa.Nmf(genomes, max_iter=100000, rank=nfactors, update='divergence', objective='div', test_conv= 30)
    nmf_fit = nmf()
    W = nmf_fit.basis()
    H = nmf_fit.coef()
    return W, H

def BootstrapCancerGenomes(genomes):
    np.random.seed() # Every time initiate a random seed so that all processors don't get the same seed
    #normalize the data 
    a = pd.DataFrame(genomes.sum(0))  #performing the sum of each column. variable a store the sum
    a = a.transpose()  #transfose the value so that if gets a proper dimention to normalize the data
    repmat = pd.concat([a]*genomes.shape[0])  #normalize the data to get the probility of each datapoint to perform the "random.multinomial" operation
    normGenomes = genomes/np.array(repmat)      #part of normalizing step
    
    
    #Get the normGenomes as Matlab/ alternation of the "mnrnd" fuction in Matlap
    #do the Boostraping 
    dataframe = pd.DataFrame() #declare an empty variable to populate with the Bootstrapped data
    for i in range(0,normGenomes.shape[1]):
        #print a.iloc[:,i]
        #print normGenomes.iloc[:,i]
        dataframe[i]=list(np.random.multinomial(a.iloc[:,i], normGenomes.iloc[:,i], 1)[0])
        
        
    return dataframe


def nmf(genomes=1, totalProcesses=1):   
    #tic = time.time()
    genomes = pd.DataFrame(genomes) #creating/loading a dataframe/matrix
    bootstrapGenomes= BootstrapCancerGenomes(genomes)
    bootstrapGenomes[bootstrapGenomes<0.0001]= 0.0001
    W, H = nnmf(bootstrapGenomes,totalProcesses)  #uses custom function nnmf
    #print ("initital W: ", W); print("\n");
    #print ("initial H: ", H); print("\n");
    W = np.array(W)
    H = np.array(H)
    total = W.sum(axis=0)[np.newaxis]
    #print ("total: ", total); print("\n");
    W = W/total
    H = H*total.T
    #print ("process " +str(totalProcesses)+" continues please wait... ")
    #print ("execution time: {} seconds \n".format(round(time.time()-tic), 2))    
    
    return W, H
# NMF version for the multiprocessing library
def pnmf(pool_constant=1, genomes=1, totalProcesses=1):
    tic = time.time()
    genomes = pd.DataFrame(genomes) #creating/loading a dataframe/matrix
    bootstrapGenomes= BootstrapCancerGenomes(genomes)
    bootstrapGenomes[bootstrapGenomes<0.0001]= 0.0001
    W, H = nnmf(bootstrapGenomes,totalProcesses)  #uses custom function nnmf
    #print ("initital W: ", W); print("\n");
    #print ("initial H: ", H); print("\n");
    W = np.array(W)
    H = np.array(H)
    total = W.sum(axis=0)[np.newaxis]
    #print ("total: ", total); print("\n");
    W = W/total
    H = H*total.T
    print ("process " +str(totalProcesses)+" continues please wait... ")
    print ("execution time: {} seconds \n".format(round(time.time()-tic), 2))
    return W, H


def parallel_runs(genomes=1, totalProcesses=1, iterations=1,  n_cpu=-1, verbose = False):
    if verbose:
        print ("Process "+str(totalProcesses)+ " is in progress\n===================================>")
    if n_cpu==-1:
        pool = multiprocessing.Pool()
    else:
        pool = multiprocessing.Pool(processes=n_cpu)
        
  
    pool_nmf=partial(pnmf, genomes=genomes, totalProcesses=totalProcesses)
    result_list = pool.map(pool_nmf, range(iterations)) 
    pool.close()
    pool.join()
    return result_list

############################################################## FUNCTION ONE ##########################################
def split_list(lst, splitlenth):
    newlst = []
    for i in range(0, len(lst), splitlenth):
        try: 
            newlst.append([lst[i], lst[i+1]])
        
        except: 
            newlst.append([lst[i]])
            
    return newlst


################################################################### FUNCTION ONE ###################################################################
# Calculates elementwise standard deviations from a list of matrices 
def mat_ave_std(matlst):

    matsum = np.zeros(matlst[0].shape)
    for i in matlst:
        matsum = matsum+i
    matavg = matsum/len(matlst)
    
    matvar=np.zeros(matlst[0].shape)
    for i in matlst:
        matvar = matvar+(i-matavg)**2
    matvar= matvar/len(matlst)
    matstd = matvar**(1/2)
    
    return matavg, matstd

################################################################### FUNCTION ONE ###################################################################
#function to calculate the cosine similarity
def cos_sim(a, b):
	"""Takes 2 vectors a, b and returns the cosine similarity according 
	to the definition of the dot product
    
    Dependencies: 
        *Requires numpy library. 
        *Does not require any custom function (constructed by me)
        
    Required by:
        * pairwise_cluster_raw
	"""
	dot_product = np.dot(a, b)
	norm_a = np.linalg.norm(a)
	norm_b = np.linalg.norm(b)
	return dot_product / (norm_a * norm_b)





################################################################### FUNCTION ONE ###################################################################
# function to calculate the centroids

def compute_pairwise_centroid(vec1, vec2):
    """Takes 2 vectors vec1, vec2 and returns the centroids of 
    vec1 and vec2 as a vector named "centroids". Here, the "centroid"
    vector is a list type variable. For better understanding please the run 
    code and check the variables in the "test of function/example section below 
    the function"
    
    Dependencies:
        *Does not require any custom function (constructed by me)
        
    Required by:
        *pairwise_cluster_init 
        *pairwise_cluster_elong
        
	"""
    
    centroids= []  
    for i in range(0, len(vec1)):
        centroid= (vec1[i]+vec2[i])/2
        centroids.append(centroid)
        
    return centroids


################################################################### FUNCTION  ###################################################################
def pairwise_cluster_raw(mat1=([0]), mat2=([0]), mat1T=([0]), mat2T=([0])):  # the matrices (mat1 and mat2) are used to calculate the clusters and the lsts will be used to store the members of clusters
    
    """ Takes a pair of matrices mat1 and mat2 as arguments. Both of the matrices should have the 
    equal shapes. The function makes a partition based clustering (the number of clusters is equal 
    to the number of colums of the matrices, and not more column is assigned into a cluster from 
    a single matrix). It return the list of clusters  as "lstCluster" and the list of clusters 
    based on their indeces of the vectors in their original matrices. Please run the 
    test of function/example code provided below the for better understanding. 
    
     Dependencies:
        *cos_sim
        
    Required by:
        *pairwise_cluster_init 
        *pairwise_cluster_elong
    
    
    """
    con_mat = np.zeros((mat1.shape[1],mat2.shape[1]))
    for i in range(0, mat1.shape[1]):
        for j in range(0,mat2.shape[1]):
            con_mat[i, j] = cos_sim(mat1[:,i], mat2[:,j])  #used custom function
    #debug
    #print (con_mat); print("\n")
        
    lstCluster=[]
    lstClusterT=[]
    idxPair= []  
    
    
    for a in range(0,mat1.shape[1]):
    
        i,j=np.unravel_index(con_mat.argmax(), con_mat.shape) 
        lstCluster.append([mat1[:,i], mat2[:,j]])
        idxPair.append([i,j])   #for debugging
        lstClusterT.append([mat1T[i,:], mat2T[j, :]])
        con_mat[i,:]=0
        con_mat[:,j]=0
        

        
    
    return lstCluster, idxPair, lstClusterT
         





################################################################### FUNCTION  ###################################################################
def pairwise_cluster_init(matPair, matPairT):
    
    """Takes a list of a pair of matrices, "matPair". It run the "pairwise_cluster_raw" inside
    it and returns a list that contains the list of cluster and the list of the corresponding 
    centroids of the each clusters. 
    
    Dependencies:
        *compute_pairwise_centroid
        *pairwise_cluster_raw
        
    Required by:
        *cluster_init
        
    """
    
    mat1 = matPair[0]; mat2 = matPair[1]
    mat1T = matPairT[0]; mat2T = matPairT[1]
    
    lstCluster,idxPairs, lstClusterT= pairwise_cluster_raw(mat1, mat2, mat1T, mat2T)   #used custom function "

    
    lstCen=[]
    for i in lstCluster: 
                
        lstCen.append(compute_pairwise_centroid(i[0],i[1]))
    return [lstCluster, np.array(lstCen), lstClusterT]





################################################################### FUNCTION  ###################################################################    
def cluster_init(listOfArrays, listOfArraysT):
    
    """Takes an array of list of matrix pairs "listOfArrays" (see the example below the function). 
    It returns a list of list of clusters-centroids pairs which are used for the next iteration 
    where "cluster_elong" is used . 
    
    Dependencies:
        *pairwise_cluster_init
    
    Required by: 
        *find_clusters
    """
    
    fulllist=[] 
    for i,j in zip(listOfArrays, listOfArraysT):
        #i an j contains have the similar structure as matPair and matPairT, respectively. see "pairwise_cluster_init".
        
        if len(i)>1:
             newlst=pairwise_cluster_init(i, j)  #custom function 
             
            
        else: 
            oddMat=[]#store the information the odd member/last matrix
            oddcen=[]
            oddMatT =[]
            for k in range(0,i[0].shape[1]):
                oddMat.append([i[0][:,k]])
                oddcen.append(i[0][:,k])
                oddMatT.append([j[0][k,:]])
            newlst = [oddMat, list(oddcen), oddMatT] 
            #print ("The odd member cannot be clustered in this round")
        
        fulllist.append(newlst)
    return fulllist


  
  
################################################################### FUNCTION  ###################################################################
    
def pairwise_cluster_elong(clust1, clust2, cen1, cen2, clust1T, clust2T):
    
    """ Takes a pair of clusters clust1, clust2 and the curresponding 
    centroids cen1, cen2. It merges the list of clusters to make a bigger 
    clusters with a double member in each cluster and computes the conbined 
    centroids for the correstponding clusters. It retrunts a list which contains 
    the list of the clusters "clusterNew" and the corresponding list of their
    centroids "cenNew"
    
     Dependencies:
        *compute_pairwise_centroid
        *pairwise_cluster_raw
        
    Required by:
        *cluster_elong
    """
    
    mat1=np.zeros([len(cen1[0]), len(cen1)])  # get the matrix size equal to datapoints or mutaion types / number of processes or ranks
    mat2=np.zeros([len(cen2[0]), len(cen2)])  # same as above for the matrix 2
    
    # the length of the list  in the first iteration will have one 
    

    
    
    for i in range(0, mat1.shape[1]):
        
        # the length of the list  in the first iteration will have one. We need to put use list1 
        
        mat1[:,i]= cen1[i] # populate the matrix with the calculated centroids
        mat2[:,i]= cen2[i]  # same as above for the matrix 2 
    
        
    lstCluster,idxPairs, lstClusterT = pairwise_cluster_raw(mat1, mat2, mat1.T, mat2.T)   #used custom function "pairwise_cluster_raw
    
    #the list of new cluster
    clusterNew = []
    cenNew = []
    clusterNewT = []
    for k in idxPairs:
        x=(k[0])
        y=(k[1])
        #print (x, y)
        newList = clust1[x]+clust2[y]
        newListT = clust1T[x] + list(clust2T[y])
        newClust = compute_pairwise_centroid(cen1[x], cen2[y])
        clusterNew.append(newList)
        cenNew.append(newClust)
        clusterNewT.append(newListT)
        
    return [clusterNew, cenNew, clusterNewT]
        
    



################################################################### FUNCTION  ###################################################################
def cluster_elong(listOfArrays):
    
    """Takes a list of list of clusters-centroids pairs "listOfArrays" and returns
    a list of list of clusters-centroids pairs (members in each cluster are double in 
    count compared to the previous clusters). The output is used for the next iteration 
    until there is only one cluster-centroid function in the list. 
    
    
    Dependencies:
        *pairwise_cluster_elong
    
    Required by: 
        *find_clusters
    """
    
    fulllist=[]
    
    
    for i in listOfArrays:
        
      
        

        
        if len(i)>1:
             clust1, clust2, cen1, cen2, clust1T, clust2T = i[0][0], i[1][0], i[0][1], i[1][1], i[0][2], i[1][2]
             newlst=pairwise_cluster_elong(clust1, clust2,  cen1, cen2, clust1T, clust2T)  #custom function 
             
             
            
        else: 
            newlst = [i[0][0],i[0][1], i[0][2]]
            
    
            
        
        fulllist.append(newlst)
        
    return fulllist


################################################################### FUNCTION  ###################################################################

#####################################################
#Contvert the list of clusters to list of dataframes
#No description given since the function is quite strait forward
#This function is required to execute the "find_clusters" function. 


def to_dataframes(clusters):
    listOfClusters=[]
    for i in clusters:
        listOfClusters.append(pd.DataFrame(i).T)
    return listOfClusters







################################################################### FUNCTION  ###################################################################
    
def find_clusters_v1(matList, matListT):
    
    """Takes a list of matrices "listOfMatrices" as argument. All of the matrices should have the 
    equal shapes. The function makes a partition based clustering (the number of clusters is equal 
    to the number of colums of the matrices, and not more column is assigned into a cluster from 
    a single matrix). It return the list of clusters  as "clusters". Please run the 
    test of function/example code provided below the for better understanding.  
    """
    
    W= split_list(matList, 2)
    H= split_list(matListT, 2)
    
    iteration="first"
    clusterSizeDifference=1  #Flag
    while clusterSizeDifference>0:
        #print ("processing")  ############################# for debugging 
        if  iteration=="first":
            listOfMatrices = cluster_init(W, H)
            listOfMatrices= split_list(listOfMatrices, 2)
            iteration = "next"
        else: 
            before = len(listOfMatrices[0][0][0][0])
            listOfMatrices = cluster_elong(listOfMatrices)
            listOfMatrices = split_list(listOfMatrices, 2)
            after = len(listOfMatrices[0][0][0][0])
            clusterSizeDifference = after-before
    clusters =  listOfMatrices[0][0][0]
    clustersT = listOfMatrices[0][0][2]
    
    
    
    listOfClusters = to_dataframes(clusters)
    listOfClustersT = to_dataframes(clustersT)
    
    




# =============================================================================
#    Calculation of Silhoutte coefficient    
# =============================================================================
    #from sklearn import metrics
    
    
    count = 0
    labels=[]
    clusters =[]
    for i in listOfClusters:
        
        clusters.append(i.T)
        for k in i:
            labels.append(count)
        count= count+1
    
    
    array = pd.concat(clusters, axis=0, ignore_index=True)
    
    try:
        SilhouetteCoefficients = metrics.silhouette_samples(array, labels, metric='cosine')
    
        
    
    except:
        SilhouetteCoefficients = np.ones((len(labels),1))
        
        
        
        
    avgSilhouetteCoefficients = np.mean(SilhouetteCoefficients)
    
    #clusterSilhouetteCoefficients 
    splitByCluster = np.array_split(SilhouetteCoefficients, len( listOfClusters))
    clusterSilhouetteCoefficients = np.array([])
    for i in splitByCluster:
        clusterSilhouetteCoefficients=np.append(clusterSilhouetteCoefficients, np.mean(i))
        
    
    
    return listOfClusters, listOfClustersT, avgSilhouetteCoefficients, clusterSilhouetteCoefficients
        


def analysis_signatures(genomes=[0], startprocesses =2, endprocesses=4, totalIterations= 10, verbose=False, n_cpu=-1 ):
    
    results = []
    
    for i in range(startprocesses , endprocesses+1, 1):
          
        processes=i
        
        #print ("\nnumber of process is: {} \n===================================>".format(processes) )
        
        genomeErrors, genomesReconstructed, Wall, Hall = extract(genomes=genomes, totalProcesses=i , totalIterations=totalIterations, verbose=verbose, n_cpu=n_cpu)
       
       
            
        
        
        W= np.array_split(Wall, totalIterations, axis=1)
        H= np.array_split(Hall, totalIterations, axis=0)
        
              
        
        
        processclust, exposerclust, avgSilhouetteCoefficients, clusterSilhouetteCoefficients= find_clusters_v1(W, H)
        
       
        
        #meanGenomeErrors = np.mean(genomeErrors, axis=2)
        #meanGenomeReconstructed = np.mean(genomesReconstructed)    
        
        # computing the avg and std of the processes and exposures:
        
        processAvg = np.zeros((genomes.shape[0], processes))
        exposureAvg = np.zeros((processes, genomes.shape[1]))
        processStd = np.zeros((genomes.shape[0], processes))
        exposureStd = np.zeros((processes, genomes.shape[1]))
        
        for i in range(0, processes):
            processAvg[:,i]=np.mean(processclust[i], axis=1)
            processStd[:,i] = np.std(processclust[i], axis=1)
            exposureAvg[i,:] = np.mean(exposerclust[i], axis=1)
            exposureStd[i,:] = np.std(exposerclust[i], axis=1)
            
        results.append([genomes, processAvg, exposureAvg, processStd, exposureStd, avgSilhouetteCoefficients, clusterSilhouetteCoefficients, genomeErrors, genomesReconstructed, Wall, Hall, processes]) 
        
    return results


def cluster_similarity(mat1=([0]), mat2=([0])):  # the matrices (mat1 and mat2) are used to calculate the clusters and the lsts will be used to store the members of clusters
    
    """ Takes a pair of matrices mat1 and mat2 as arguments. Both of the matrices should have the 
    equal shapes. The function makes a partition based clustering (the number of clusters is equal 
    to the number of colums of the matrices, and not more column is assigned into a cluster from 
    a single matrix). It return the list of clusters  as "lstCluster" and the list of clusters 
    based on their indeces of the vectors in their original matrices. Please run the 
    test of function/example code provided below the for better understanding. 
    
     Dependencies:
        *cos_sim
        
    Required by:
        *pairwise_cluster_init 
        *pairwise_cluster_elong
    
    
    """
    con_mat = np.zeros((mat1.shape[1],mat2.shape[1]))
    for i in range(0, mat1.shape[1]):
        for j in range(0,mat2.shape[1]):
            con_mat[i, j] = cos_sim(mat1[:,i], mat2[:,j])  #used custom function
    #debug
    #print (con_mat); print("\n")
    similarity_mat   = pd.DataFrame(con_mat.copy())  
    lstCluster=[]
    idxPair= []  
    similarity = []
    
    for a in range(0,mat1.shape[1]):
        
        i,j=np.unravel_index(con_mat.argmax(), con_mat.shape) 
        similarity.append(con_mat.max())
        lstCluster.append([mat1[:,i], mat2[:,j]])
        idxPair.append([i,j])   #for debugging
        
        con_mat[i,:]=0
        con_mat[:,j]=0
        
     
        
    
    return  similarity_mat, idxPair, similarity, lstCluster



#############################################################################################################
#################################### Functions to add sparsity in the Exposures #############################
#############################################################################################################

def parameterized_objective2_custom(x, signatures, samples):
    rec = np.dot(signatures, x)
    y = LA.norm(samples-rec)
    return y


def constraints1(x, samples):
    sumOfSamples=np.sum(samples, axis=0)
    #print(sumOfSamples)
    #print(x)
    result = sumOfSamples-(np.sum(x))
    #print (result)
    return result


def create_bounds(idxOfZeros, samples, numOfSignatures):
    total = np.sum(samples)
    b = (0.0, float(total))
    lst =[b]*numOfSignatures
    
    for i in idxOfZeros:
        lst[i] = (0.0, 0.0) 
    
    return lst 





# to do the calculation, we need: W, samples(one column), H for the specific sample, tolerence

def remove_all_single_signatures(W, H, genomes):
    # make the empty list of the successfull combinations
    successList = [0,[],0] 
    # get the cos_similarity with sample for the oringinal W and H[:,i]
    originalSimilarity= cos_sim(genomes, np.dot(W, H))
    # make the original exposures of specific sample round
    oldExposures = np.round(H)
    
    # set the flag for the while loop
    if len(oldExposures[np.nonzero(oldExposures)])>1:
        Flag = True
    else: 
        Flag = False
        return oldExposures
    # The while loop starts here
    while Flag: 
        
        # get the list of the indices those already have zero values
        if len(successList[1]) == 0:
            initialZerosIdx = list(np.where(oldExposures==0)[0]) 
            #get the indices to be selected
            selectableIdx = list(np.where(oldExposures>0)[0]) 
        elif len(successList[1]) > 1: 
            initialZerosIdx = list(np.where(successList[1]==0)[0]) 
            #get the indices to be selected
            selectableIdx = list(np.where(successList[1]>0)[0])
        else:
            print("iteration is completed")
            #break
        
        
        # get the total mutations for the given sample
        maxmutation = round(np.sum(genomes))
        
        # new signature matrix omiting the column for zero
        #Winit = np.delete(W, initialZerosIdx, 1)
        Winit = W[:,selectableIdx]
        
        # set the initial cos_similarity
        record  = [0.11, []] 
        # get the number of current nonzeros
        l= Winit.shape[1]
        
        for i in range(l):
            #print(i)
            loopSelection = list(range(l))
            del loopSelection[i]
            #print (loopSelection)
            W1 = Winit[:,loopSelection]
           
            
            #initialize the guess
            x0 = np.random.rand(l-1, 1)*maxmutation
            x0= x0/np.sum(x0)*maxmutation
            
            #set the bounds and constraints
            bnds = create_bounds([], genomes, W1.shape[1]) 
            cons1 ={'type': 'eq', 'fun': constraints1, 'args':[genomes]} 
            
            #the optimization step
            sol = minimize(parameterized_objective2_custom, x0, args=(W1, genomes),  bounds=bnds, constraints =cons1, tol=1e-15)
            
            #print (sol.success)
            #print (sol.x)
            
            #convert the newExposure vector into list type structure
            newExposure = list(sol.x)
            
            #insert the loopZeros in its actual position 
            newExposure.insert(i, 0)
            
            #insert zeros in the required position the newExposure matrix
            initialZerosIdx.sort()
            for zeros in initialZerosIdx:
                newExposure.insert(zeros, 0)
            
            # get the maximum value the new Exposure
            maxcoef = max(newExposure)
            idxmaxcoef = newExposure.index(maxcoef)
            
            newExposure = np.round(newExposure)
            
            
            if np.sum(newExposure)!=maxmutation:
                newExposure[idxmaxcoef] = round(newExposure[idxmaxcoef])+maxmutation-sum(newExposure)
                
            
            newSample = np.dot(W, newExposure)
            newSimilarity = cos_sim(genomes, newSample) 
             
            difference = originalSimilarity - newSimilarity
            #print(originalSimilarity)
            #print(newSample)
            #print(newExposure)
            #print(newSimilarity)
            
            #print(difference)
            #print (newExposure)
            #print (np.round(H))
            #print ("\n\n")
             
            if difference<record[0]:
                record = [difference, newExposure, newSimilarity]
            
            
        #print ("This loop's selection is {}".format(record))
        
        if record[0]>0.01:   
            Flag=False
        elif len(record[1][np.nonzero(record[1])])==1:
            successList = record 
            Flag=False
        else:
            successList = record
        #print("The loop selection is {}".format(successList))
        
        #print (Flag)
        #print ("\n\n")
    
    #print ("The final selection is {}".format(successList))
    
    if len(successList[1])==0:
        successList = [0.0, oldExposures, originalSimilarity]
    
    return successList[1]
    


def remove_all_single_signatures_pool(indices, W, exposures, totoalgenomes):
    i = indices
    H = exposures[:,i]
    genomes= totoalgenomes[:,i]
    # make the empty list of the successfull combinations
    successList = [0,[],0] 
    # get the cos_similarity with sample for the oringinal W and H[:,i]
    originalSimilarity= cos_sim(genomes, np.dot(W, H))
    # make the original exposures of specific sample round
    oldExposures = np.round(H)
    
    # set the flag for the while loop
    if len(oldExposures[np.nonzero(oldExposures)])>1:
        Flag = True
    else: 
        Flag = False
        return oldExposures
    # The while loop starts here
    while Flag: 
        
        # get the list of the indices those already have zero values
        if len(successList[1]) == 0:
            initialZerosIdx = list(np.where(oldExposures==0)[0]) 
            #get the indices to be selected
            selectableIdx = list(np.where(oldExposures>0)[0]) 
        elif len(successList[1]) > 1: 
            initialZerosIdx = list(np.where(successList[1]==0)[0]) 
            #get the indices to be selected
            selectableIdx = list(np.where(successList[1]>0)[0])
        else:
            print("iteration is completed")
            #break
        
        
        # get the total mutations for the given sample
        maxmutation = round(np.sum(genomes))
        
        # new signature matrix omiting the column for zero
        #Winit = np.delete(W, initialZerosIdx, 1)
        Winit = W[:,selectableIdx]
        
        # set the initial cos_similarity
        record  = [0.11, []] 
        # get the number of current nonzeros
        l= Winit.shape[1]
        
        for i in range(l):
            #print(i)
            loopSelection = list(range(l))
            del loopSelection[i]
            #print (loopSelection)
            W1 = Winit[:,loopSelection]
           
            
            #initialize the guess
            x0 = np.random.rand(l-1, 1)*maxmutation
            x0= x0/np.sum(x0)*maxmutation
            
            #set the bounds and constraints
            bnds = create_bounds([], genomes, W1.shape[1]) 
            cons1 ={'type': 'eq', 'fun': constraints1, 'args':[genomes]} 
            
            #the optimization step
            sol = minimize(parameterized_objective2_custom, x0, args=(W1, genomes),  bounds=bnds, constraints =cons1, tol=1e-15)
            
            #print (sol.success)
            #print (sol.x)
            
            #convert the newExposure vector into list type structure
            newExposure = list(sol.x)
            
            #insert the loopZeros in its actual position 
            newExposure.insert(i, 0)
            
            #insert zeros in the required position the newExposure matrix
            initialZerosIdx.sort()
            for zeros in initialZerosIdx:
                newExposure.insert(zeros, 0)
            
            # get the maximum value the new Exposure
            maxcoef = max(newExposure)
            idxmaxcoef = newExposure.index(maxcoef)
            
            newExposure = np.round(newExposure)
            
            
            if np.sum(newExposure)!=maxmutation:
                newExposure[idxmaxcoef] = round(newExposure[idxmaxcoef])+maxmutation-sum(newExposure)
                
            
            newSample = np.dot(W, newExposure)
            newSimilarity = cos_sim(genomes, newSample) 
             
            difference = originalSimilarity - newSimilarity
            #print(originalSimilarity)
            #print(newSample)
            #print(newExposure)
            #print(newSimilarity)
            
            #print(difference)
            #print (newExposure)
            #print (np.round(H))
            #print ("\n\n")
             
            if difference<record[0]:
                record = [difference, newExposure, newSimilarity]
            
            
        #print ("This loop's selection is {}".format(record))
        
        if record[0]>0.01:   
            Flag=False
        elif len(record[1][np.nonzero(record[1])])==1:
            successList = record 
            Flag=False
        else:
            successList = record
        #print("The loop selection is {}".format(successList))
        
        #print (Flag)
        #print ("\n\n")
    
    #print ("The final selection is {}".format(successList))
    
    if len(successList[1])==0:
        successList = [0.0, oldExposures, originalSimilarity]
    
    #print ("one sample completed")
    return successList[1]








#############################################################################################################
#################################### Decipher Signatures ###################################################
#############################################################################################################

def decipher_signatures(genomes=[0], i=1, totalIterations=1, cpu=-1, mut_context="96"):
    m = mut_context
    
    tic = time.time()
    # The initial values accumute the results for each number of 
    totalMutationTypes = genomes.shape[0];
    totalGenomes = genomes.shape[1];
    totalProcesses = i
    
    print ("Extracting signature {} for mutation type {}".format(i, m))  # m is for the mutation context
    
    
    
    ##############################################################################################################################################################################         
    ############################################################# The parallel processing takes place here #######################################################################  
    ##############################################################################################################################################################################         
    results = parallel_runs(genomes=genomes, totalProcesses=totalProcesses, iterations=totalIterations,  n_cpu=cpu, verbose = False)
        
    toc = time.time()
    print ("Time taken to collect {} iterations for {} signatures is {} seconds".format(totalIterations , i, round(toc-tic, 2)))
    ##############################################################################################################################################################################       
    ######################################################### The parallel processing ends here ##################################################################################      
    ##############################################################################################################################################################################        
    
    
    ################### Achieve the best clustering by shuffling results list using a few iterations ########### 
    avgSilhouetteCoefficients = -1.1
    clusterSilhouetteCoefficients = [0]
    processclust=[0]
    exposerclust=[0]
    finalWall=[0]
    finalHall = [0]
    finalgenomeErrors=[0]
    finalgenomesReconstructed = [0]
    
    for k in range(25):
        shuffle(results)
        Wall = np.zeros((totalMutationTypes, totalProcesses * totalIterations));
        #print (Wall.shape)
        Hall = np.zeros((totalProcesses * totalIterations, totalGenomes));
        genomeErrors = np.zeros((totalMutationTypes, totalGenomes, totalIterations));
        genomesReconstructed = np.zeros((totalMutationTypes, totalGenomes, totalIterations))
        
        processCount=0
        for j in range(len(results)):
            W = results[j][0]
            H = results[j][1]
            genomeErrors[:, :, j] = genomes -  np.dot(W,H);
            genomesReconstructed[:, :, j] = np.dot(W,H);
            #print ("W", W.shape)
            Wall[ :, processCount : (processCount + totalProcesses) ] = W;
            Hall[ processCount : (processCount + totalProcesses), : ] = H;
            processCount = processCount + totalProcesses;
        #print (Wall.shape, Hall.shape)
        
        
        W= np.array_split(Wall, totalIterations, axis=1)
        H= np.array_split(Hall, totalIterations, axis=0)
           
        
        loop_processclust, loop_exposerclust, loop_avgSilhouetteCoefficients, loop_clusterSilhouetteCoefficients= find_clusters_v1(W, H)
        
        #print ("stability", loop_avgSilhouetteCoefficients)
        #look for clusters which gives the best SilhouetteCoefficients
        if loop_avgSilhouetteCoefficients>avgSilhouetteCoefficients:
            avgSilhouetteCoefficients=loop_avgSilhouetteCoefficients
            clusterSilhouetteCoefficients = loop_clusterSilhouetteCoefficients
            processclust = loop_processclust
            exposerclust = loop_exposerclust
            finalWall = Wall
            finalHall = Hall
            finalgenomeErrors = genomeErrors 
            finalgenomesReconstructed = genomesReconstructed
            
       
            
            
        
        #print(avgSilhouetteCoefficients)
    
       
    
    #meanGenomeErrors = np.mean(genomeErrors, axis=2)
    #meanGenomeReconstructed = np.mean(genomesReconstructed)    
    
    # computing the avg and std of the processes and exposures:
    processes=i #renamed the i as "processes"
    processAvg = np.zeros((genomes.shape[0], processes))
    exposureAvg = np.zeros((processes, genomes.shape[1]))
    processStd = np.zeros((genomes.shape[0], processes))
    exposureStd = np.zeros((processes, genomes.shape[1]))
    
    for j in range(0, processes):
        processAvg[:,j]=np.mean(processclust[j], axis=1)
        processStd[:,j] = np.std(processclust[j], axis=1)
        exposureAvg[j,:] = np.mean(exposerclust[j], axis=1)
        exposureStd[j,:] = np.std(exposerclust[j], axis=1)






    return  processAvg, exposureAvg, processStd, exposureStd, avgSilhouetteCoefficients, clusterSilhouetteCoefficients, finalgenomeErrors, finalgenomesReconstructed, finalWall, finalHall, processes





################################################### Generation of probabilities for each processes given to A mutation type ############################################
def probabilities(W, H):  
    
    # setting up the indices 
    rows = W.index
    cols = H.columns
    sigs = W.columns
    
    W = np.array(W)
    H= np.array(H)
    # rebuild the original matrix from the estimated W and H 
    genomes = np.dot(W,H)
    
    
    result = 0
    for i in range(H.shape[1]): #here H.shape is the number of sample
        
        M = genomes[:,i][np.newaxis]
        #print (M.shape)
        
        probs = W*H[:,i]/M.T
        #print ("Sum of Probabilities for Sample {} is : ".format(i+1))
        #print(probs)
        #print ("Sum of Probabilities for Sample {} is: ".format(i+1))
        #print(probs.sum(axis=1)[np.newaxis].T) 
        
        
        probs = pd.DataFrame(probs)
        probs.columns = sigs
        col1 = [cols[i]]*len(rows)
        probs.insert(loc=0, column='Sample', value=col1)
        probs.insert(loc=1, column='Mutations', value = rows)
        #print (probs)
        #print ("\n")
        if i!=0:
            result = pd.concat([result, probs], axis=0)
        else:
            result = probs
        
    return result
#########################################################################################################################################################################        





        
##########################################################################################################################################################################
#################################################################### Result Exporting  ###################################################################################
##########################################################################################################################################################################


def export_information(loopResults, mutation_context, output, index, colnames):
    
    #print(colnames)
    
    i = loopResults[-1]
    
        
    #print ("The mutaion type is", mutation_type)    
    m = mutation_context
    if not (m=="DINUC"or m=="INDEL"):
        mutation_type = "SNV"
        
    else:
        mutation_type = m
    # Create the neccessary directories
    subdirectory = output+"/All solutions/"+str(i)+" "+ mutation_type+ " Signature"
    if not os.path.exists(subdirectory):
        os.makedirs(subdirectory)
    
    
    
    #Export the loopResults as pickle objects
    
    #resultname = "signature"+str(i)
    
    # =============================================================================
    #         f = open(output+"/pickle_objects/"+resultname, 'wb')
    #         
    #         pickle.dump(loopResults, f)
    #         f.close()
    # =============================================================================
            
       
    #preparing the column and row indeces for the Average processes and exposures:  
    listOfSignatures = []
    letters = list(string.ascii_uppercase)
    letters.extend([i+b for i in letters for b in letters])
    letters = letters[0:i]
    
    for j,l in zip(range(i),letters)  :
        listOfSignatures.append("Signature "+l)
    listOfSignatures = np.array(listOfSignatures)
    
    #print("print listOfSignares ok", listOfSignatures)
        
    
    #Extract the genomes, processAVG, processStabityAvg
    genome= loopResults[0]
    #print ("genomes are ok", genome)
    processAvg= (loopResults[1])
    exposureAvg= (loopResults[2])
    processStabityAvg= (loopResults[5])
    #print ("processStabityAvg is ok", processStabityAvg)
    
    # Calculating and listing the reconstruction error, process stability and signares to make a csv file at the end
    reconstruction_error = LA.norm(genome-np.dot(processAvg, exposureAvg), 'fro')/LA.norm(genome, 'fro')
    
    
    #print ("reconstruction_error is ok", reconstruction_error)
    #print (' Initial reconstruction error is {} and the process stability is {} for {} signatures\n\n'.format(reconstruction_error, round(processStabityAvg,4), i))
    # Preparing the results to export as textfiles for each signature
    
    #First exporting the Average of the processes
    processAvg= pd.DataFrame(processAvg)
    processes = processAvg.set_index(index)
    processes.columns = listOfSignatures
    processes = processes.rename_axis("signatures", axis="columns")
    #print(processes)
    #print("process are ok", processes)
    processes.to_csv(subdirectory+"/processes.txt", "\t", index_label=[processes.columns.name]) 
    
    #Second exporting the Average of the exposures
    exposureAvg = pd.DataFrame(exposureAvg)
    exposures = exposureAvg.set_index(listOfSignatures)
    exposures.columns = colnames
    exposures = exposures.rename_axis("samples", axis="columns")
    #print("exposures are ok", exposures)
    exposures.to_csv(subdirectory+"/exposures.txt", "\t", index_label=[exposures.columns.name]) 
       
    fh = open(output+"/results_stat.csv", "a") 
    print ('The reconstruction error is {} and the process stability is {} for {} signatures\n\n'.format(reconstruction_error, round(processStabityAvg,4), i))
    fh.write('{}, {}, {}\n'.format(i, reconstruction_error, processStabityAvg))
    fh.close()
    
    
   
    ########################################### PLOT THE SIGNATURES ################################################
    
    if m=="DINUC" or m=="78":
        plot.plotDBS(subdirectory+"/processes.txt", subdirectory+"/Signature_plot" , "", "78", True)
    elif m=="INDEL" or m=="83":
        plot.plotID(subdirectory+"/processes.txt", subdirectory+"/Signature_plot" , "", "94", True)
    else:
        plot.plotSBS(subdirectory+"/processes.txt", subdirectory+"/Signature_plot", "", m, True)
     
        
    processAvg = pd.read_csv(subdirectory+"/processes.txt", sep="\t", index_col=0)
    exposureAvg = pd.read_csv(subdirectory+"/exposures.txt", sep="\t", index_col=0)
    probability = probabilities(processAvg, exposureAvg)
    probability=probability.set_index("Sample")
    probability.to_csv(subdirectory+"/probabilities.txt", "\t") 
    





#############################################################################################################
#################################### STABILITY VS RECONSTRUCTION ERROR PLOT #################################
#############################################################################################################

def stabVsRError(csvfile, outputfile, title):
    
    data = pd.read_csv(csvfile, sep=",")


    # Create some mock data
    t = np.array(data.iloc[:,0])
    data1 = np.array(data.iloc[:,1])  #reconstruction error
    data2 = np.array(data.iloc[:,2])  #process stability
    
    
    #selecting the optimum signature
    datanew = data[data[' Process stability']>0.85]
    datanew = datanew[(datanew['Number of signature'] == datanew['Number of signature'].max())]
    optimum_signature = int(datanew['Number of signature'])
    
    
    #to the make the shadows with the optimum number of signatues in the plot
    shadow_start = optimum_signature-0.2
    shadow_end=optimum_signature+0.2
    
    fig, ax1 = plt.subplots(num=None, figsize=(10, 6), dpi=300, facecolor='w', edgecolor='k')
    
    color = 'tab:red'
    ax1.set_xlabel('Number of Signatures')
    ax1.set_ylabel('Relative Reconstruction Error', color=color)
    ax1.set_title(title)
    ax1.plot(t, data1, marker='o', color=color)
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.xaxis.set_ticks(np.arange(min(t), max(t)+1, 1))
    ax1.axvspan(shadow_start, shadow_end, alpha=0.20, color='#ADD8E6')
    # manipulate the y-axis values into percentage 
    vals = ax1.get_yticks()
    ax1.set_yticklabels(['{:,.0%}'.format(x) for x in vals])
    
    ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
    color = 'tab:blue'
    ax2.set_ylabel('Process Stability', color=color)  # we already handled the x-label with ax1
    ax2.plot(t, data2, marker='o', color=color)
    ax2.tick_params(axis='y', labelcolor=color)
    
    fig.tight_layout()  # otherwise the right y-label is slightly clipped
    #plt.show()
    plt.savefig(outputfile+'/stability.pdf')    
    
    plt.close()
    return optimum_signature


